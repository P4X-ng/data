// SPDX-License-Identifier: MIT
// staging/pnic/pnic_agg.c
// Host-side aggregator: maps multiple shared-memory regions (one per fake VM NIC)
// and forwards frames into the local pCPU executor.

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <pthread.h>
#include <sys/mman.h>
#include <time.h>

#include "../../src/packetfs/gram/pfs_gram.h"
#include "../../src/packetfs/memory/pfs_hugeblob.h"
#include "../../src/packetfs/pcpu/pfs_pcpu.h"
#include "pnic_shm.h"

static inline uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }
static void pin_cpu(int cpu){ if(cpu<0) return; cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu,&set); sched_setaffinity(0,sizeof(set),&set); }

typedef struct {
    void* base;              // mapped region base
    size_t bytes;            // mapping size
    PnicRegionHdr* hdr;
    uint32_t* slots;
    PfsGramDesc* frames;     // frames[ring_size * dpf]
} Endpoint;

typedef struct {
    // configuration
    int threads; int pin_first;
    pfs_pcpu_op_t op; uint8_t imm; const char* prog_s; pfs_pcpu_op_t prog_ops[16]; uint8_t prog_imms[16]; size_t prog_n;
    double duration; const char* huge_dir; const char* blob_name; size_t blob_bytes;
    // state
    Endpoint* eps; int ep_n;
    PfsHugeBlob blob;
    _Atomic uint64_t bytes_eff; _Atomic uint64_t frames_cons; _Atomic int stop;
} Ctx;

static int parse_prog(const char* s, pfs_pcpu_op_t* ops, uint8_t* imms, size_t max){
    if(!s||!*s) return 0; char* dup=strdup(s); if(!dup) return 0; size_t n=0; char*save=NULL; for(char*t=strtok_r(dup,",",&save); t && n<max; t=strtok_r(NULL,",",&save)){
        char* name=t; char* c=strchr(t,':'); unsigned long v=0; if(c){ *c='\0'; v=strtoul(c+1,NULL,0);} pfs_pcpu_op_t op=PFS_PCPU_OP_XOR_IMM8; uint8_t iv=(uint8_t)v;
        if(!strcmp(name,"fnv")||!strcmp(name,"fnv64")) { op=PFS_PCPU_OP_CHECKSUM_FNV64; iv=0; }
        else if(!strcmp(name,"crc32c")) { op=PFS_PCPU_OP_CHECKSUM_CRC32C; iv=0; }
        else if(!strcmp(name,"xor")) { op=PFS_PCPU_OP_XOR_IMM8; }
        else if(!strcmp(name,"add")) { op=PFS_PCPU_OP_ADD_IMM8; }
        else if(!strcmp(name,"counteq")) { op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
        else continue; ops[n]=op; imms[n]=iv; n++; }
    free(dup); return (int)n;
}

typedef struct { Ctx* ctx; int thr_id; int ep_first; int ep_last; } WorkerArgs;

static void* worker_fn(void* arg){
    WorkerArgs* wa=(WorkerArgs*)arg; Ctx* c=wa->ctx; int cpu = c->pin_first + wa->thr_id; pin_cpu(cpu);
    while(!__atomic_load_n(&c->stop,__ATOMIC_RELAXED)){
        for(int i=wa->ep_first;i<wa->ep_last;i++){
            Endpoint* e = &c->eps[i]; PnicRegionHdr* h=e->hdr; uint32_t* slots=e->slots; PfsGramDesc* frames=e->frames; uint32_t dpf=h->dpf; uint32_t idx;
            while(pnic_pop(h, slots, &idx)){
                PfsGramDesc* d = &frames[(size_t)idx * dpf];
                if(c->prog_n>0){ for(size_t k=0;k<c->prog_n;k++){ pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(c->blob.addr, c->blob.size, d, dpf, c->prog_ops[k], c->prog_imms[k], 1469598103934665603ULL, &mm); __atomic_fetch_add(&c->bytes_eff, mm.bytes_touched, __ATOMIC_RELAXED); }}
                else { pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(c->blob.addr, c->blob.size, d, dpf, c->op, c->imm, 1469598103934665603ULL, &mm); __atomic_fetch_add(&c->bytes_eff, mm.bytes_touched, __ATOMIC_RELAXED); }
                __atomic_fetch_add(&c->frames_cons, 1ull, __ATOMIC_RELAXED);
            }
        }
        struct timespec ts={0,1000000}; nanosleep(&ts,NULL);
    }
    return NULL;
}

int main(int argc, char** argv){
    // Defaults
    int threads=4, pin_first=0; double duration=5.0; size_t blob_bytes=1ull<<30; const char* huge_dir="/mnt/huge1G"; const char* blob_name="pnic_agg_blob";
    pfs_pcpu_op_t op=PFS_PCPU_OP_XOR_IMM8; uint8_t imm=255; const char* prog_s=NULL;
    // Endpoints passed as comma-separated list of files
    const char* eps_s=NULL;

    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--endpoints")&&i+1<argc) eps_s=argv[++i];
        else if(!strcmp(argv[i],"--threads")&&i+1<argc) threads=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--pin-first")&&i+1<argc) pin_first=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_bytes=(size_t)strtoull(argv[++i],NULL,10)<<20;
        else if(!strcmp(argv[i],"--huge-dir")&&i+1<argc) huge_dir=argv[++i];
        else if(!strcmp(argv[i],"--blob-name")&&i+1<argc) blob_name=argv[++i];
        else if(!strcmp(argv[i],"--op")&&i+1<argc){ const char* s=argv[++i]; if(!strcmp(s,"xor")) op=PFS_PCPU_OP_XOR_IMM8; else if(!strcmp(s,"add")) op=PFS_PCPU_OP_ADD_IMM8; else if(!strcmp(s,"crc32c")) op=PFS_PCPU_OP_CHECKSUM_CRC32C; else if(!strcmp(s,"fnv")) op=PFS_PCPU_OP_CHECKSUM_FNV64; else if(!strcmp(s,"counteq")) op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
        else if(!strcmp(argv[i],"--imm")&&i+1<argc) imm=(uint8_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--prog")&&i+1<argc) prog_s=argv[++i];
        else { fprintf(stderr,"Usage: %s --endpoints /dev/shm/a,/dev/shm/b [--threads N] [--pin-first C] [--duration S] [--blob-mb MB] [--op xor|add|crc32c|fnv|counteq] [--imm N] [--prog STR]\n", argv[0]); return 2; }
    }
    if(!eps_s){ fprintf(stderr,"--endpoints required\n"); return 2; }

    Ctx ctx; memset(&ctx,0,sizeof(ctx)); ctx.threads=threads; ctx.pin_first=pin_first; ctx.op=op; ctx.imm=imm; ctx.prog_s=prog_s; ctx.duration=duration; ctx.huge_dir=huge_dir; ctx.blob_name=blob_name; ctx.blob_bytes=blob_bytes;
    if(prog_s) ctx.prog_n = (size_t)parse_prog(prog_s, ctx.prog_ops, ctx.prog_imms, 16);

    // Map blob
    if(pfs_hugeblob_map(ctx.blob_bytes, ctx.huge_dir, ctx.blob_name, &ctx.blob)!=0){ perror("hugeblob_map"); return 1; }
    pfs_hugeblob_set_keep(&ctx.blob, 1);

    // Parse endpoints
    // Count commas
    int ep_n=1; for(const char* p=eps_s; *p; ++p) if(*p==',') ep_n++;
    ctx.eps = (Endpoint*)calloc((size_t)ep_n, sizeof(Endpoint)); ctx.ep_n=ep_n;
    char* dup=strdup(eps_s); char* save=NULL; int idx=0; for(char* tok=strtok_r(dup, ",", &save); tok && idx<ep_n; tok=strtok_r(NULL, ",", &save)){
        const char* path=tok; int fd=open(path, O_RDWR); if(fd<0){ fprintf(stderr,"open %s: %s\n", path, strerror(errno)); return 1; }
        // We don't know size; map header first, then compute full size using header values (assume ftruncate already done by producer)
        off_t fsz = lseek(fd, 0, SEEK_END); if(fsz<=0){ fprintf(stderr,"%s size invalid\n", path); close(fd); return 1; }
        void* base = mmap(NULL, (size_t)fsz, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0); close(fd);
        if(base==MAP_FAILED){ fprintf(stderr,"mmap %s: %s\n", path, strerror(errno)); return 1; }
        PnicRegionHdr* h=(PnicRegionHdr*)base; if(h->magic != 0x504e4943u || h->version != 1){ fprintf(stderr,"bad region %s\n", path); return 1; }
        ctx.eps[idx].base=base; ctx.eps[idx].bytes=(size_t)fsz; ctx.eps[idx].hdr=h; ctx.eps[idx].slots=pnic_slots(base); ctx.eps[idx].frames=(PfsGramDesc*)pnic_frames_base(base);
        idx++;
    }
    free(dup);

    // Launch workers
    int t = ctx.threads>0? ctx.threads:1; pthread_t* tids=(pthread_t*)calloc((size_t)t, sizeof(pthread_t));
    int per = (ctx.ep_n + t - 1)/t; for(int i=0;i<t;i++){ WorkerArgs* wa=(WorkerArgs*)calloc(1,sizeof(WorkerArgs)); wa->ctx=&ctx; wa->thr_id=i; wa->ep_first=i*per; wa->ep_last=wa->ep_first+per; if(wa->ep_first>=ctx.ep_n){ wa->ep_first=wa->ep_last=ctx.ep_n; } if(wa->ep_last>ctx.ep_n) wa->ep_last=ctx.ep_n; pthread_create(&tids[i], NULL, worker_fn, wa); }

    // stats loop
    uint64_t t0=now_ns(); uint64_t next=t0+500000000ull; uint64_t tend=t0 + (uint64_t)(ctx.duration*1e9); uint64_t last_b=0, last_f=0;
    while(now_ns() < tend){ struct timespec ts={0,20000000}; nanosleep(&ts,NULL); uint64_t now=now_ns(); if(now<next) continue; next += 500000000ull; uint64_t b=__atomic_load_n(&ctx.bytes_eff,__ATOMIC_RELAXED); uint64_t f=__atomic_load_n(&ctx.frames_cons,__ATOMIC_RELAXED); double dt=0.5; double mbps=((double)(b-last_b)/1e6)/dt; double fps=((double)(f-last_f)/dt); fprintf(stdout,"[pnic_agg] eps=%d bytes=%.1f MB (%.1f MB/s) frames=%llu (%.0f/s)\n", ctx.ep_n, (double)b/1e6, mbps, (unsigned long long)f, fps); last_b=b; last_f=f; }

    __atomic_store_n(&ctx.stop, 1, __ATOMIC_RELAXED); for(int i=0;i<t;i++){ pthread_join(tids[i], NULL); }
    for(int i=0;i<ctx.ep_n;i++){ munmap(ctx.eps[i].base, ctx.eps[i].bytes); }
    free(ctx.eps); free(tids); pfs_hugeblob_unmap(&ctx.blob);
    uint64_t total_b=__atomic_load_n(&ctx.bytes_eff,__ATOMIC_RELAXED); double secs=(now_ns()-t0)/1e9; if(secs<=0.0) secs=ctx.duration; fprintf(stdout,"[pnic_agg DONE] bytes=%.1f MB secs=%.3f avg=%.1f MB/s\n", (double)total_b/1e6, secs, ((double)total_b/1e6)/secs);
    return 0;
}
