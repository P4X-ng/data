#pragma once
#include <stdint.h>

#define YEET_MAGIC 0x59454554u /* 'YEET' */
#define YEET_VER   0x01

/* v0 header: little-endian fields */
#pragma pack(push, 1)
typedef struct {
    uint32_t magic;   /* YEET_MAGIC */
    uint8_t  ver;     /* YEET_VER */
    uint8_t  flags;   /* reserved */
    uint16_t hdr_len; /* bytes of header (for future) */
    uint64_t seq;     /* packet sequence */
    uint16_t len;     /* payload length following header */
} yeet_hdr_v0_t;
#pragma pack(pop)

static inline void yeet_fill_hdr(yeet_hdr_v0_t *h, uint64_t seq, uint16_t len) {
    h->magic = YEET_MAGIC;
    h->ver = YEET_VER;
    h->flags = 0;
    h->hdr_len = (uint16_t)sizeof(yeet_hdr_v0_t);
    h->seq = seq;
    h->len = len;
}
