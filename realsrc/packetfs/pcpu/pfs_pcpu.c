#define _GNU_SOURCE
#include "pfs_pcpu.h"
#include <time.h>
#include <string.h>

static inline uint64_t now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

uint64_t pfs_fnv1a64_update(uint64_t h, const uint8_t* p, size_t n) {
  // FNV-1a 64
  if (!p || n == 0) return h;
  for (size_t i = 0; i < n; ++i) {
    h ^= p[i];
    h *= 1099511628211ULL;
  }
  return h;
}

int pfs_pcpu_apply(void* base,
                   size_t blob_size,
                   const PfsGramDesc* descs,
                   size_t n,
                   pfs_pcpu_op_t op,
                   uint8_t imm8,
                   uint64_t fnv_seed,
                   pfs_pcpu_metrics_t* outm)
{
  if (!base || !descs || n == 0) return -1;
  pfs_pcpu_metrics_t m;
  memset(&m, 0, sizeof(m));

  const uint8_t imm = imm8;
  uint64_t t0 = now_ns();

  for (size_t i = 0; i < n; ++i) {
    uint64_t off = descs[i].offset;
    uint32_t len = descs[i].len;
    m.bytes_total += (uint64_t)len;

    // Bounds check
    if (off >= blob_size) continue;
    if (off + (uint64_t)len > blob_size) {
      // clamp to end of blob
      len = (uint32_t)(blob_size - off);
    }
    if (len == 0) continue;

    uint8_t* ptr = (uint8_t*)base + off;
    __builtin_prefetch(ptr, 0, 1);

    switch (op) {
      case PFS_PCPU_OP_CHECKSUM_FNV64: {
        fnv_seed = pfs_fnv1a64_update(fnv_seed, ptr, len);
        m.bytes_touched += len;
      } break;

      case PFS_PCPU_OP_XOR_IMM8: {
        // scalar path; vectorization can come later
        for (uint32_t j = 0; j < len; ++j) ptr[j] ^= imm;
        m.bytes_touched += len;
      } break;

      case PFS_PCPU_OP_ADD_IMM8: {
        for (uint32_t j = 0; j < len; ++j) ptr[j] = (uint8_t)(ptr[j] + imm);
        m.bytes_touched += len;
      } break;

      default:
        // unknown op
        break;
    }

    m.desc_count++;
  }

  uint64_t t1 = now_ns();
  m.ns = (t1 - t0);
  m.cycles = 0; // optional: rdtsc if desired later
  if (op == PFS_PCPU_OP_CHECKSUM_FNV64) m.checksum_out = fnv_seed;

  if (outm) *outm = m;
  return 0;
}

