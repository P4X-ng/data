#include "prp.h"
#include <stdint.h>

uint32_t prp32(uint32_t x, uint32_t key){
    x ^= key * 0x9E3779B9u;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    x ^= (key ^ 0x85EBCA77u);
    return x;
}

