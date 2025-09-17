#ifndef PFS_GRAM_H
#define PFS_GRAM_H

#include <stddef.h>
#include <stdint.h>

#define PFS_GRAM_MAGIC 0x47524650u /* 'PFRG' little-endian in memory */

#pragma pack(push,1)
typedef struct {
    uint32_t magic;        // PFS_GRAM_MAGIC
    uint16_t version;      // 1
    uint16_t flags;        // bit0: payload_present, bit1: reserved
    uint64_t gram_seq;     // gram sequence number
    uint32_t desc_count;   // number of descriptors following
    uint32_t header_len;   // bytes of header+desc table (not including any payload slab)
    uint64_t payload_len;  // total bytes if payload slab is present; 0 for offset-only grams
    uint32_t crc32;        // optional CRC over header+desc (0 if disabled)
    uint32_t reserved;     // pad to 32 bytes
} PfsGramHeader;
#pragma pack(pop)

#pragma pack(push,1)
typedef struct {
    uint64_t offset;       // offset into blob
    uint32_t len;          // length of segment
    uint32_t flags;        // reserved; align to 16 bytes
} PfsGramDesc;
#pragma pack(pop)

// Fill a PfsGramHeader structure with provided fields. Returns sizeof(PfsGramHeader).
size_t pfs_gram_header_write(PfsGramHeader* hdr,
                             uint64_t gram_seq,
                             uint32_t desc_count,
                             uint64_t payload_len,
                             uint16_t flags);

// Generate 'count' descriptors deterministically using a seed, constrained by blob_size and max_len.
// Alignment must be power of two; offsets will be aligned to 'align'. Returns number generated (count on success).
size_t pfs_gram_gen_descs(uint64_t seed,
                          size_t blob_size,
                          uint32_t count,
                          uint32_t max_len,
                          uint32_t align,
                          PfsGramDesc* out);

#endif // PFS_GRAM_H

