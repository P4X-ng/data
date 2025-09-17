#include <stdint.h>

// PacketFS execution endpoints (native in-process library)
// Implements basic ALU operations mirroring micro_executor behavior.

#ifdef __cplusplus
extern "C" {
#endif

uint32_t pfs_execute_add(uint32_t a, uint32_t b) {
    return a + b;
}

uint32_t pfs_execute_sub(uint32_t a, uint32_t b) {
    return a - b;
}

uint32_t pfs_execute_mul(uint32_t a, uint32_t b) {
    return a * b;
}

#ifdef __cplusplus
}
#endif

// Batched add loop for benchmarking
// acc <- start; repeat count times: acc += inc; return acc
// Uses 64-bit count to allow very large loops.
#ifdef __cplusplus
extern "C" {
#endif
#include <stddef.h>
#include <inttypes.h>
uint32_t pfs_add_loop_u32(uint32_t start, uint32_t inc, uint64_t count) {
    uint32_t acc = start;
    // Unroll by 4 for a bit of speed without relying on compiler auto-unroll
    while (count >= 4) {
        acc += inc;
        acc += inc;
        acc += inc;
        acc += inc;
        count -= 4;
    }
    while (count > 0) {
        acc += inc;
        count--;
    }
    return acc;
}
#ifdef __cplusplus
}
#endif

