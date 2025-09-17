#ifndef PFS_PCPU_H
#define PFS_PCPU_H

#include <stdint.h>
#include <stddef.h>
#include "../gram/pfs_gram.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
  PFS_PCPU_OP_CHECKSUM_FNV64 = 1,
  PFS_PCPU_OP_XOR_IMM8       = 2,
  PFS_PCPU_OP_ADD_IMM8       = 3,
  PFS_PCPU_OP_COUNT_EQ_IMM8  = 4,
  PFS_PCPU_OP_CHECKSUM_CRC32C= 5,
  PFS_PCPU_OP_HIST8          = 6
} pfs_pcpu_op_t;

typedef struct {
  uint64_t bytes_total;    // sum of descriptor lengths (even if some skipped)
  uint64_t bytes_touched;  // within-bounds bytes actually processed
  uint64_t desc_count;     // number of descriptors processed
  uint64_t checksum_out;   // final FNV-1a if op=CHECKSUM
  uint64_t cycles;         // optional (0 if not captured)
  uint64_t ns;             // elapsed nanoseconds for the apply()
} pfs_pcpu_metrics_t;

uint64_t pfs_fnv1a64_update(uint64_t seed, const uint8_t* p, size_t len);

int pfs_pcpu_apply(void* base,
                   size_t blob_size,
                   const PfsGramDesc* descs,
                   size_t n,
                   pfs_pcpu_op_t op,
                   uint8_t imm8,
                   uint64_t fnv_seed,
                   pfs_pcpu_metrics_t* outm);

#ifdef __cplusplus
}
#endif

#endif // PFS_PCPU_H

