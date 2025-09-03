# PacketFS Protocol Specification

## Overview

PacketFS is a novel transport protocol that transmits **offsets** instead of data, pointing to synchronized data structures shared between communicating nodes. This approach aims to achieve significant performance improvements over traditional TCP/UDP by eliminating data movement overhead.

## Architecture

### Core Concept
- **Synchronized Data Pools**: Both endpoints maintain identical copies of reference data
- **Offset Transmission**: Instead of sending actual data, nodes exchange 8/16/32-bit offsets
- **Layer 2 Operation**: Direct Ethernet frames with custom EtherType (0x1337)
- **Tiered Protocol Stack**: L1/L2/L3 tiers with different reference sizes and purposes

### Design Principles
- **Zero-copy References**: Point to data rather than copying it
- **High-frequency Transmission**: Optimized for sustained >10k FPS
- **Minimal Protocol Overhead**: Compact bitstream encoding
- **Hardware Acceleration Ready**: C extension with GPU integration points

## Protocol Structure

### Frame Format

```
Ethernet Frame:
┌─────────────────┬─────────────────┬──────────────┬─────────────────────┬─────┐
│ Dest MAC (6)    │ Src MAC (6)     │ EtherType(2) │ PacketFS Payload    │ FCS │
│ ff:ff:ff:ff:ff:ff│ aa:bb:cc:dd:ee:ff│    0x1337    │ (variable length)   │ (4) │
└─────────────────┴─────────────────┴──────────────┴─────────────────────┴─────┘

PacketFS Payload:
┌───────────────────────────────────────────────────────────────────────────────┐
│ Tier-Switched Bitstream + Optional SYNC Units                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Bitstream Encoding

#### Tier Switching (2 bits)
- `00`: L1 tier (8-bit refs)
- `01`: L2 tier (16-bit refs)  
- `10`: L3 tier (32-bit refs)
- `11`: Reserved for future control opcodes

#### Reference Encoding
- **L1 References**: 8 bits, pointing to byte-level data
- **L2 References**: 16 bits, pointing to word-level structures
- **L3 References**: 32 bits, pointing to large data blocks

#### Tier Persistence
- Current tier remains active until explicitly changed
- Reduces protocol overhead for homogeneous reference streams

### Synchronization Protocol

#### Window-Based Synchronization
```
Window Configuration:
- window_pow2: Power of 2 defining window size (default: 16 → 65,536 refs)
- window_crc16: Enable/disable CRC validation per window
```

#### SYNC Frame Format
```
SYNC Frame (CRC enabled):
┌────────────┬─────────────┬─────────────┐
│ SYNC_MARK  │ Window ID   │ CRC16       │
│ 0xF0 (1)   │ (2 bytes)   │ (2 bytes)   │
└────────────┴─────────────┴─────────────┘

SYNC Frame (CRC disabled):
┌────────────┬─────────────┐
│ SYNC_MARK  │ Window ID   │
│ 0xF0 (1)   │ (2 bytes)   │
└────────────┴─────────────┘
```

#### Synchronization Behavior
- SYNC frames generated automatically at window boundaries
- Window ID increments monotonically (with 16-bit rollover)
- CRC16-CCITT calculated over all references in the window
- Decoder validates sync frames for stream integrity

### Control Opcodes

#### Current Opcodes
- `0xF0`: SYNC_MARK - Synchronization frame marker
- `0xF1`: SYNC_ACK - Synchronization acknowledgment (reserved)

#### Future Control Extensions
- NACK frames for error recovery
- Flow control mechanisms
- Congestion notifications
- Route optimization hints

## State Machines

### Encoder State Machine

```
┌─────────────┐
│ INITIALIZED │
└─────┬───────┘
      │
      ▼
┌─────────────┐  pack_refs()  ┌──────────────┐
│ ENCODING    │◄──────────────┤ ACCUMULATING │
└─────┬───────┘               └──────┬───────┘
      │                              │
      │ window_boundary_reached      │
      ▼                              │
┌─────────────┐  emit_sync()         │
│ SYNC_READY  │──────────────────────┘
└─────────────┘
```

### Decoder State Machine

```
┌─────────────┐
│ LISTENING   │
└─────┬───────┘
      │ receive_frame()
      ▼
┌─────────────┐  scan_for_sync()  ┌──────────────┐
│ PROCESSING  │─────────────────→ │ SYNC_FOUND   │
└─────┬───────┘                   └──────┬───────┘
      │                                  │
      │ no_sync_found                    │ validate_crc()
      ▼                                  ▼
┌─────────────┐                   ┌──────────────┐
│ DATA_READY  │                   │ SYNCHRONIZED │
└─────────────┘                   └──────────────┘
```

## Performance Characteristics

### Current Benchmarks (C Extension)

| Configuration | Throughput | Avg Latency | Efficiency |
|---------------|------------|-------------|------------|
| L1 64B refs   | 34,226 fps | 0.6 μs      | 98.5%      |
| L2 256B refs  | 32,978 fps | 0.7 μs      | 97.8%      |
| L3 1KB refs   | 35,408 fps | 0.6 μs      | 99.2%      |
| Stress Test   | 3,971 fps  | N/A         | 79.4%      |

### Scaling Characteristics
- **Linear scaling** with reference density
- **Sub-microsecond latency** for small payloads
- **>99% bit-packing efficiency** at L3 tier
- **Sustained 4k+ FPS** under stress conditions

## Error Handling

### CRC Validation
- CRC16-CCITT polynomial: `0x1021`
- Initial value: `0xFFFF`
- Calculated over all references in window
- Window boundary enforcement prevents partial corruption

### Error Recovery (Future)
- NACK mechanism for requesting retransmission
- Sliding window protocol for flow control
- Decoder resynchronization on CRC mismatch
- Graceful degradation under packet loss

## Implementation Notes

### C Extension Requirements
- **O3 optimization** for maximum performance
- **C11 standard** compliance
- **Bounds checking** for buffer overflow prevention
- **Endianness handling** for cross-platform compatibility

### Pseudo-Random Permutation (PRP)
```c
// Placeholder PRP implementation
static inline uint32_t prp32(uint32_t x, uint32_t key) {
    x ^= key * 0x9E3779B9u;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    x ^= (key ^ 0x85EBCA77u);
    return x;
}
```

### GPU Integration Points

#### Potential CUDA Acceleration
- **Bitstream packing**: Parallel reference encoding
- **CRC calculation**: Hardware-accelerated checksums
- **PRP operations**: Vectorized permutation calculations
- **Batch processing**: Multi-frame parallel encoding

#### C API Hooks (Future)
```c
// GPU-accelerated bitpacking interface
typedef struct {
    uint32_t *refs;
    size_t ref_count;
    int tier;
    uint8_t *output;
    size_t output_size;
} gpu_bitpack_request_t;

int gpu_bitpack_encode(gpu_bitpack_request_t *request);
int gpu_bitpack_decode(gpu_bitpack_request_t *request);
```

## Testing Strategy

### Unit Tests
- ✅ CRC16-CCITT edge cases and known vectors
- ✅ Protocol encoder/decoder state transitions  
- ✅ Tier switching and window boundary handling
- ✅ Reference counter overflow and rollover
- ✅ Sync frame generation and validation

### Integration Tests  
- ✅ End-to-end veth pair communication
- ✅ Error injection and corruption handling
- ✅ Frame reordering robustness
- ✅ Multi-window synchronization validation

### Performance Tests
- ✅ Latency histogram analysis (p50/p95/p99)
- ✅ Prometheus metrics integration
- ✅ Baseline regression detection
- ✅ Stress testing under load

### Future Tests
- ⏳ Cross-hardware evaluation (Intel/Realtek/virtual)
- ⏳ Multi-tier switching performance
- ⏳ Large payload handling (1MB+ refs)
- ⏳ GPU acceleration benchmarks

## Metrics and Monitoring

### Prometheus Metrics
```
# Latency tracking
packetfs_latency_seconds{operation="encode|decode", tier="0|1|2"}

# Throughput measurement  
packetfs_throughput_pps{direction="tx|rx"}

# Error counters
packetfs_crc_errors_total
packetfs_sync_frames_total

# Resource utilization
packetfs_bits_packed_total{tier="0|1|2"}
packetfs_frame_size_bytes
```

### Performance Baselines
- JSON-formatted benchmark results
- Automated regression detection (>5% degradation)
- Historical trend analysis
- Cross-platform performance comparison

## Future Enhancements

### Protocol Extensions
1. **NACK/Retry Mechanism**: Reliable delivery option
2. **Multicast Support**: One-to-many offset distribution
3. **Route Optimization**: Dynamic path selection
4. **Compression**: Reference deduplication and encoding

### Hardware Acceleration
1. **CUDA Implementation**: GPU-accelerated bitpacking
2. **DPDK Integration**: Kernel-bypass networking
3. **RDMA Support**: Direct memory access
4. **FPGA Offloading**: Hardware protocol processing

### Ecosystem Integration  
1. **Container Orchestration**: Kubernetes networking plugin
2. **Service Mesh**: Istio/Envoy proxy integration
3. **Database Clustering**: Distributed cache coherency
4. **ML/AI Pipelines**: High-speed model synchronization

## References

1. **C Extension API**: `src/native/bitpack.c`
2. **Protocol Implementation**: `src/packetfs/protocol.py` 
3. **Performance Tests**: `tests/test_metrics.py`
4. **Integration Tests**: `tests/test_integration.py`
5. **Baseline Results**: `baseline_results_updated.json`

---

**Protocol Version**: 0.1.0  
**Last Updated**: August 29, 2025  
**Status**: Experimental/Research
