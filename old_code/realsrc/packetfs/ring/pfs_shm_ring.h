#pragma once
#include <stdint.h>
#include <stdatomic.h>
#include <stddef.h>

// Cacheline alignment helper (64B typical on x86_64)
#ifndef PFS_CACHELINE
#define PFS_CACHELINE 64
#endif

// Single-producer single-consumer ring of u32 slots (indices), lock-free
// - size must be a power of two
// - slots contain indices into an external frame array
// - producer thread: only calls pfs_spsc_push
// - consumer thread: only calls pfs_spsc_pop

typedef struct {
    uint32_t size;      // number of entries (power of two)
    uint32_t mask;      // size - 1
    _Atomic uint32_t head __attribute__((aligned(PFS_CACHELINE))); // consumer position
    _Atomic uint32_t tail __attribute__((aligned(PFS_CACHELINE))); // producer position
    uint32_t* slots __attribute__((aligned(PFS_CACHELINE)));       // length = size
} PfsSpscRing;

// Create ring with given size (must be power of two). Returns 0 on success.
int pfs_spsc_create(PfsSpscRing* r, uint32_t size);
// Destroy the ring and free memory.
void pfs_spsc_destroy(PfsSpscRing* r);

// Try to enqueue one value. Returns 1 on success, 0 if the ring is full.
static inline int pfs_spsc_push(PfsSpscRing* r, uint32_t v){
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    uint32_t head = atomic_load_explicit(&r->head, memory_order_acquire);
    if(((tail + 1) & r->mask) == head) return 0; // full
    r->slots[tail] = v;
    atomic_store_explicit(&r->tail, (tail + 1) & r->mask, memory_order_release);
    return 1;
}

// Try to dequeue one value. Returns 1 on success and stores to *out, 0 if empty.
static inline int pfs_spsc_pop(PfsSpscRing* r, uint32_t* out){
    uint32_t head = atomic_load_explicit(&r->head, memory_order_relaxed);
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_acquire);
    if(head == tail) return 0; // empty
    *out = r->slots[head];
    atomic_store_explicit(&r->head, (head + 1) & r->mask, memory_order_release);
    return 1;
}

