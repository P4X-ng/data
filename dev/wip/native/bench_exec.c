#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// extern from packet_exec_lib.c
extern uint32_t pfs_add_loop_u32(uint32_t start, uint32_t inc, uint64_t count);

static inline uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

// CRC16-CCITT (poly 0x1021, init 0xFFFF), byte-wise, big-endian
static uint16_t crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; ++j) {
            if (crc & 0x8000) crc = (uint16_t)((crc << 1) ^ 0x1021);
            else crc <<= 1;
        }
    }
    return crc;
}

int main(int argc, char **argv) {
    uint64_t start_ops = (argc > 1) ? strtoull(argv[1], NULL, 10) : 1048576ull; // 1 Mi
    int window_pow2 = (argc > 2) ? atoi(argv[2]) : 16; // 64k
    double budget_sec = (argc > 3) ? atof(argv[3]) : 60.0;

    const uint64_t win_size = 1ull << window_pow2;
    uint8_t *win_refs = (uint8_t*)malloc(win_size);
    if (!win_refs) { fprintf(stderr, "alloc failed\n"); return 1; }
    memset(win_refs, 1, win_size);
    const uint16_t expected_crc = crc16_ccitt(win_refs, win_size);

    printf("Native Windowed Batch Benchmark (no Python)\n");
    printf("=========================================\n");
    printf("Window size: 2^%d = %llu\n", window_pow2, (unsigned long long)win_size);
    printf("Time budget: %.1f s\n\n", budget_sec);
    printf("%12s  %8s  %10s  %12s  %4s\n", "ops", "windows", "elapsed(s)", "ops/s", "crc");

    double total = 0.0;
    uint64_t ops = start_ops;
    while (total < budget_sec) {
        uint64_t windows = ops / win_size;
        uint64_t remainder = ops % win_size;
        uint32_t acc = 0;

        uint64_t t0 = now_ns();
        for (uint64_t w = 0; w < windows; ++w) {
            // Batch ALU
            acc = pfs_add_loop_u32(acc, 1, win_size);
            // CRC over window
            volatile uint16_t crc = crc16_ccitt(win_refs, win_size);
            if (crc != expected_crc) {
                printf("CRC MISMATCH on window %llu!\n", (unsigned long long)w);
                break;
            }
        }
        if (remainder) {
            acc = pfs_add_loop_u32(acc, 1, remainder);
            // Optional: CRC of partial window (not a full sync) — skip for now
        }
        uint64_t t1 = now_ns();
        double elapsed = (double)(t1 - t0) / 1e9;
        total += elapsed;
        double ops_per_sec = (elapsed > 0.0) ? (double)ops / elapsed : 0.0;
        printf("%12llu  %8llu  %10.4f  %12.0f  %4s\n",
               (unsigned long long)ops,
               (unsigned long long)windows,
               elapsed, ops_per_sec, "OK");

        ops *= 2ull;
    }

    printf("\nTotal time: %.2f s\n", total);
    free(win_refs);
    return 0;
}

