#include "pfs_gram.h"

#include <stddef.h>
#include <stdint.h>

static inline uint64_t xorshift64star(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }

size_t pfs_gram_header_write(PfsGramHeader* hdr,
                             uint64_t gram_seq,
                             uint32_t desc_count,
                             uint64_t payload_len,
                             uint16_t flags){
    hdr->magic = PFS_GRAM_MAGIC;
    hdr->version = 1;
    hdr->flags = flags;
    hdr->gram_seq = gram_seq;
    hdr->desc_count = desc_count;
    hdr->payload_len = payload_len;
    hdr->crc32 = 0; // optional; left 0 for now
    hdr->reserved = 0;
    hdr->header_len = (uint32_t)(sizeof(PfsGramHeader) + desc_count * sizeof(PfsGramDesc));
    return sizeof(PfsGramHeader);
}

size_t pfs_gram_gen_descs(uint64_t seed,
                          size_t blob_size,
                          uint32_t count,
                          uint32_t max_len,
                          uint32_t align,
                          PfsGramDesc* out){
    if(!out || count==0) return 0;
    if(align==0) align = 1;
    // Ensure align is power of two
    if((align & (align-1))!=0){ // round up to next power of two
        uint32_t a=1; while(a < align) a <<= 1; align = a;
    }
    uint64_t x = seed?seed:0x9E3779B97F4A7C15ULL;
    for(uint32_t i=0;i<count;i++){
        x = xorshift64star(x);
        uint64_t r = x;
        uint32_t len = (uint32_t)(1 + (r % (max_len?max_len:1)));
        // Align and bound offset
        x = xorshift64star(x);
        uint64_t off = (x % (blob_size?blob_size:1));
        off &= ~((uint64_t)align - 1ULL);
        if(off + len > blob_size){
            if(len > blob_size) len = (uint32_t)blob_size;
            off = blob_size - len;
            off &= ~((uint64_t)align - 1ULL);
        }
        out[i].offset = off;
        out[i].len = len;
        out[i].flags = 0;
    }
    return count;
}

