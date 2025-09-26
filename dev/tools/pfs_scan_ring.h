#pragma once
// pfs_scan_ring.h — Minimal shared ring for scan tasks over a mapped region
// Layout (single-producer single-consumer for simplicity):
// [RingHdr][slots array uint32_t][slab data...]
// A slot holds the offset into the slab where a record begins.
// A record format:
//   uint32_t n; // tasks count
//   ScanTask n times
// Task: (dst IPv4 LE, port, proto)

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct __attribute__((packed)) {
  uint32_t dst_ipv4; // LE (inet addr as uint32)
  uint16_t port;     // network order not required here; user decides
  uint8_t  proto;    // 6=tcp, 17=udp
  uint8_t  pad;
} ScanTask;

typedef struct {
  uint32_t slots;        // power of two
  uint32_t mask;         // slots-1
  volatile uint32_t head;// consumer
  volatile uint32_t tail;// producer
  uint32_t data_offset;  // bytes from base to slab start
  uint32_t region_bytes; // total mapped bytes
} RingHdr;

static inline uint32_t ring_count(const RingHdr* h){
  uint32_t t = __atomic_load_n(&h->tail, __ATOMIC_ACQUIRE);
  uint32_t hd= __atomic_load_n(&h->head, __ATOMIC_RELAXED);
  return (t - hd) & h->mask;
}

#ifdef __cplusplus
}
#endif
