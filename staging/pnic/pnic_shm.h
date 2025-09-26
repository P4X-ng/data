// SPDX-License-Identifier: MIT
// staging/pnic/pnic_shm.h
// Shared-memory region layout for fake pNIC producers (VMs) and host aggregator.
// Single-producer single-consumer ring per region (one region per VM/producer).

#pragma once
#include <stdint.h>
#include <stdatomic.h>
#include <stddef.h>

// Region header placed at the beginning of the shared mapping.
typedef struct {
    uint32_t magic;           // 'PNIC' = 0x504e4943
    uint16_t version;         // 1
    uint16_t reserved0;
    uint32_t ring_size;       // entries (power of two)
    uint32_t ring_mask;       // ring_size-1
    uint32_t dpf;             // descriptors per frame
    uint32_t align;           // alignment for offsets/len
    // offsets from base
    uint64_t slots_off;       // uint32_t[ring_size]
    uint64_t frames_off;      // PfsGramDesc[ring_size * dpf]
    // indices
    _Atomic uint32_t head;    // consumer
    _Atomic uint32_t tail;    // producer
    // padding for cachelines
    uint8_t _pad[64];
} PnicRegionHdr;

// Helper to compute total bytes for a region mapping.
static inline size_t pnic_region_size(uint32_t ring_size, uint32_t dpf, size_t gram_desc_size){
    size_t slots_bytes = (size_t)ring_size * sizeof(uint32_t);
    size_t frames_bytes = (size_t)ring_size * dpf * gram_desc_size;
    size_t hdr = (sizeof(PnicRegionHdr) + 63) & ~((size_t)63);
    size_t off_slots = (hdr + 63) & ~((size_t)63);
    size_t off_frames = (off_slots + slots_bytes + 63) & ~((size_t)63);
    return off_frames + frames_bytes;
}

static inline void pnic_region_init(void* base, uint32_t ring_size, uint32_t dpf, uint32_t align, size_t gram_desc_size){
    PnicRegionHdr* r = (PnicRegionHdr*)base;
    size_t hdr = (sizeof(PnicRegionHdr) + 63) & ~((size_t)63);
    size_t off_slots = (hdr + 63) & ~((size_t)63);
    size_t off_frames = (off_slots + (size_t)ring_size * sizeof(uint32_t) + 63) & ~((size_t)63);
    r->magic = 0x504e4943u; // 'PNIC'
    r->version = 1;
    r->ring_size = ring_size;
    r->ring_mask = ring_size - 1;
    r->dpf = dpf;
    r->align = align;
    r->slots_off = off_slots;
    r->frames_off = off_frames;
    atomic_store_explicit(&r->head, 0, memory_order_relaxed);
    atomic_store_explicit(&r->tail, 0, memory_order_relaxed);
    // zero slots and frames area
    uint8_t* p = (uint8_t*)base;
    for(size_t i=0;i<(size_t)ring_size * sizeof(uint32_t);i++) p[off_slots+i]=0;
    for(size_t i=0;i<(size_t)ring_size * dpf * gram_desc_size;i++) p[off_frames+i]=0;
}

static inline uint32_t* pnic_slots(void* base){
    PnicRegionHdr* r = (PnicRegionHdr*)base;
    return (uint32_t*)((uint8_t*)base + r->slots_off);
}

// Each slot i corresponds to dpf descriptors at frames[i * dpf]
static inline void* pnic_frames_base(void* base){
    PnicRegionHdr* r = (PnicRegionHdr*)base;
    return (void*)((uint8_t*)base + r->frames_off);
}

// Push one slot index, returns 1 on success, 0 if full.
static inline int pnic_push(PnicRegionHdr* r, uint32_t* slots, uint32_t idx){
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    uint32_t head = atomic_load_explicit(&r->head, memory_order_acquire);
    if(((tail + 1) & r->ring_mask) == head) return 0;
    slots[tail] = idx;
    atomic_store_explicit(&r->tail, (tail + 1) & r->ring_mask, memory_order_release);
    return 1;
}

// Pop one slot index, returns 1 on success, 0 if empty.
static inline int pnic_pop(PnicRegionHdr* r, uint32_t* slots, uint32_t* out){
    uint32_t head = atomic_load_explicit(&r->head, memory_order_relaxed);
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_acquire);
    if(head == tail) return 0;
    *out = slots[head];
    atomic_store_explicit(&r->head, (head + 1) & r->ring_mask, memory_order_release);
    return 1;
}
