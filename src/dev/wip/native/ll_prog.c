#include <stdint.h>
// Example JIT span function: count bytes equal to imm and fold into acc
// Signature must match pfs_jit_span_fn in pfs_shm_ports_bench.c
void pfs_jit_span(uint8_t* ptr, uint32_t len, uint8_t imm, uint64_t* acc){
    uint64_t c = 0;
    for(uint32_t i=0;i<len;i++) c += (ptr[i] == imm);
    *acc ^= c;
}

