#include "pfs_shm_ring.h"
#include <stdlib.h>
#include <string.h>
#include <errno.h>

static int is_pow2(uint32_t x){ return x && ((x & (x-1)) == 0); }

int pfs_spsc_create(PfsSpscRing* r, uint32_t size){
    if(!r || !is_pow2(size)) { errno = EINVAL; return -1; }
    memset(r, 0, sizeof(*r));
    r->size = size; r->mask = size - 1;
    r->head = 0; r->tail = 0;
    // 64-byte alignment for slots array
    void* mem = NULL; if(posix_memalign(&mem, PFS_CACHELINE, sizeof(uint32_t) * size) != 0) return -1;
    r->slots = (uint32_t*)mem; memset(r->slots, 0, sizeof(uint32_t) * size);
    return 0;
}

void pfs_spsc_destroy(PfsSpscRing* r){
    if(!r) return; if(r->slots) free(r->slots); memset(r, 0, sizeof(*r));
}

