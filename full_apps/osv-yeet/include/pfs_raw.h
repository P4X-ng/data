#pragma once
#include <stdint.h>

#define PFS_ETHERTYPE 0x88B5u
#define PFS_MAGIC 0x50465331u /* 'PFS1' */

typedef struct __attribute__((packed)) {
    uint32_t magic_le;   /* PFS_MAGIC (LE) */
    uint8_t  op;         /* 0=none,1=xor,2=add,3=fnv,4=crc32c */
    uint8_t  imm;        /* immediate for xor/add/counteq */
    uint16_t flags;      /* reserved */
    uint32_t payload_len_le; /* payload bytes after this header */
    uint64_t seq_le;     /* sequence */
} pfs_hdr_t;

static inline void pfs_fill_hdr(pfs_hdr_t *h, uint64_t seq, uint32_t payload_len, uint8_t op, uint8_t imm){
    h->magic_le = 0x31334650u; /* LE('PFS1') if BE host flips, but we read as LE */
    h->op = op; h->imm = imm; h->flags = 0;
    h->payload_len_le = payload_len;
    h->seq_le = seq;
}
