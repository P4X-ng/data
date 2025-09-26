// SPDX-License-Identifier: MIT
// staging/pnic/pnic_tx_shm.c
// Simulated VM-side producer: creates a shared-memory region file and fills it with frames.
// This lets us test the host aggregator without OSv bring-up.

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <time.h>

#include "../../src/packetfs/gram/pfs_gram.h"
#include "pnic_shm.h"

static inline uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }
static inline uint64_t xorshift64(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }

static void usage(const char* a0){
    fprintf(stderr, "Usage: %s --path /dev/shm/pnic_vm_001 --ring-pow2 14 --dpf 64 --align 64 --duration 5 --blob-mb 1024\n", a0);
}

int main(int argc, char** argv){
    const char* path = NULL; uint32_t ring_pow2=14; uint32_t dpf=64; uint32_t align=64; double duration=5.0; size_t blob_bytes=1ull<<30;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--path")&&i+1<argc) path=argv[++i];
        else if(!strcmp(argv[i],"--ring-pow2")&&i+1<argc) ring_pow2=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--dpf")&&i+1<argc) dpf=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--align")&&i+1<argc) align=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_bytes=(size_t)strtoull(argv[++i],NULL,10)<<20;
        else { usage(argv[0]); return 2; }
    }
    if(!path){ usage(argv[0]); return 2; }

    uint32_t ring_sz = 1u << ring_pow2;
    size_t rbytes = pnic_region_size(ring_sz, dpf, sizeof(PfsGramDesc));

    int fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0660);
    if(fd < 0){ perror("open path"); return 1; }
    if(ftruncate(fd, (off_t)rbytes) != 0){ perror("ftruncate"); close(fd); return 1; }
    void* base = mmap(NULL, rbytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    if(base==MAP_FAILED){ perror("mmap"); close(fd); return 1; }
    close(fd);

    pnic_region_init(base, ring_sz, dpf, align, sizeof(PfsGramDesc));
    PnicRegionHdr* hdr = (PnicRegionHdr*)base; uint32_t* slots = pnic_slots(base);
    PfsGramDesc* frames = (PfsGramDesc*)pnic_frames_base(base);

    uint64_t t0=now_ns(); uint64_t tend = t0 + (uint64_t)(duration*1e9);
    uint64_t x = 0x12345678abcdefULL ^ t0; uint64_t prod=0;

    while(now_ns() < tend){
        // pick a slot index to write (round-robin frame slots)
        uint32_t tail = atomic_load_explicit(&hdr->tail, memory_order_relaxed);
        uint32_t head = atomic_load_explicit(&hdr->head, memory_order_acquire);
        if(((tail + 1) & hdr->ring_mask) == head){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue; }
        uint32_t idx = tail; // we will push this slot
        PfsGramDesc* d = &frames[(size_t)idx * dpf];
        uint64_t eff=0, prev_off=0; uint64_t base_off = blob_bytes/2;
        for(uint32_t i=0;i<dpf;i++){
            x = xorshift64(x);
            uint32_t len = (uint32_t)((x % (align? (align*4):4096)) + align); if(len > 262144u) len=262144u;
            uint64_t off = (x % (blob_bytes?blob_bytes:1)); if(align) off &= ~((uint64_t)align-1ULL);
            if(off + len > blob_bytes){ if(len > blob_bytes) len = (uint32_t)blob_bytes; off = blob_bytes - len; if(align) off &= ~((uint64_t)align-1ULL); }
            d[i].offset = off; d[i].len = len; d[i].flags = 0;
            eff += len; prev_off = off;
        }
        // publish
        slots[tail] = idx;
        atomic_store_explicit(&hdr->tail, (tail + 1) & hdr->ring_mask, memory_order_release);
        prod++;
    }

    munmap(base, rbytes);
    fprintf(stdout, "[pnic_tx_shm] produced=%llu\n", (unsigned long long)prod);
    return 0;
}
