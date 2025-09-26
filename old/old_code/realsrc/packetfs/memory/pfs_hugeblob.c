#define _GNU_SOURCE
#include "pfs_hugeblob.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/sysinfo.h>
#include <sys/types.h>
#include <unistd.h>

static size_t get_default_page_size(void){ long p = sysconf(_SC_PAGESIZE); return (p>0)?(size_t)p:4096; }

int pfs_hugeblob_map_file(const char* huge_dir, const char* name, size_t size, PfsHugeBlob* out){
    if(!huge_dir || !out) return -1;
    char path[512];
    snprintf(path,sizeof(path),"%s/%s", huge_dir, name?name:"pfs_blob");
    int fd = open(path, O_CREAT|O_RDWR, 0600);
    if(fd<0) return -1;
    if(ftruncate(fd, (off_t)size) != 0){ close(fd); /* keep file for debugging */ return -1; }
    void* addr = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    if(addr==MAP_FAILED){ int e=errno; close(fd); errno=e; return -1; }
    memset(out,0,sizeof(*out));
    out->addr = addr; out->size = size; out->fd = fd; out->hugetlbfs=1; out->page_size = 2*1024*1024; // typical; unknown in general
    snprintf(out->name,sizeof(out->name),"%s", name?name:"pfs_blob");
    snprintf(out->dir,sizeof(out->dir),"%s", huge_dir);
    out->keep_file = 0;
    return 0;
}

int pfs_hugeblob_map(size_t size, const char* huge_dir, const char* name, PfsHugeBlob* out){
    if(!out) return -1; memset(out,0,sizeof(*out));
    // Try hugetlbfs first
    if(huge_dir && pfs_hugeblob_map_file(huge_dir, name, size, out)==0){ return 0; }
    // Fallback to anonymous mapping with THP hint
    void* addr = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if(addr==MAP_FAILED) return -1;
    // Hint THP
    madvise(addr, size, MADV_HUGEPAGE);
    memset(out,0,sizeof(*out));
    out->addr=addr; out->size=size; out->fd=-1; out->hugetlbfs=0; out->page_size=get_default_page_size();
    out->keep_file = 0; out->name[0]='\0'; out->dir[0]='\0';
    return 0;
}

void pfs_hugeblob_prefault(PfsHugeBlob* blob, size_t touch_bytes){
    if(!blob || !blob->addr || blob->size==0) return;
    size_t ps = blob->page_size? blob->page_size : get_default_page_size();
    volatile uint8_t* p = (volatile uint8_t*)blob->addr;
    for(size_t off=0; off<blob->size; off += ps){
        p[off] = (uint8_t)(off/ps); // touch
        if(touch_bytes>1 && off+touch_bytes<=blob->size){ memset((void*)(p+off), (int)(off/ps), touch_bytes); }
    }
}

void pfs_hugeblob_fill(PfsHugeBlob* blob, uint64_t seed){
    if(!blob || !blob->addr || blob->size==0) return;
    uint8_t* p = (uint8_t*)blob->addr;
    // Simple xorshift64* PRNG
    uint64_t x = seed?seed:0x9E3779B97F4A7C15ULL;
    for(size_t i=0;i<blob->size;i++){
        x ^= x >> 12; x ^= x << 25; x ^= x >> 27; x *= 2685821657736338717ULL;
        p[i] = (uint8_t)(x >> 56);
    }
}

void pfs_hugeblob_unmap(PfsHugeBlob* blob){
    if(!blob) return;
    if(blob->addr && blob->size) munmap(blob->addr, blob->size);
    if(blob->hugetlbfs && blob->fd>=0){
        // Best effort cleanup: truncate to 0 unless keep_file is set
        if(!blob->keep_file){ (void)ftruncate(blob->fd, 0); }
        close(blob->fd);
    }
    memset(blob,0,sizeof(*blob));
}

void pfs_hugeblob_set_keep(PfsHugeBlob* blob, int keep){ if(!blob) return; blob->keep_file = keep ? 1 : 0; }

