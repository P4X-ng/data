#ifndef PFS_INSN_H
#define PFS_INSN_H

#include <stdint.h>
#include <stddef.h>

// EtherType for Native PFS frames (reusing protocol value 0x1337)
#ifndef ETH_P_PFS
#define ETH_P_PFS 0x1337
#endif

// 'PFSI' magic for instruction frames
#define PFSI_MAGIC 0x50465349u

#pragma pack(push,1)
typedef struct {
    uint32_t magic;      // PFSI_MAGIC
    uint16_t version;    // 1
    uint16_t flags;      // reserved
    uint64_t seq;        // frame sequence
    uint16_t insn_count; // number of instructions (1 for streaming mode)
    uint16_t reserved;   // pad to 16
} PfsInsnHdr; // 16 bytes
#pragma pack(pop)

// Opcodes (minimal set for now)
#define PFSI_MOVI  1  // MOV reg[dst] <- imm
#define PFSI_ADD   2  // ADD reg[dst] <- reg[dst] + reg[src]
#define PFSI_SUB   3  // SUB reg[dst] <- reg[dst] - reg[src]
#define PFSI_MUL   4  // MUL reg[dst] <- reg[dst] * reg[src]
#define PFSI_ADDI  5  // ADDI reg[dst] <- reg[dst] + imm

#pragma pack(push,1)
typedef struct {
    uint8_t  opcode;   // PFSI_*
    uint8_t  dst;      // destination register index
    uint8_t  src;      // source register index (for reg-reg ops)
    uint8_t  flags;    // reserved
    uint32_t imm;      // immediate for MOVI/ADDI
    uint32_t reserved; // pad to 16
} PfsInsn; // 16 bytes
#pragma pack(pop)

static inline size_t pfsi_header_write(PfsInsnHdr* h, uint64_t seq, uint16_t count){
    h->magic = PFSI_MAGIC; h->version=1; h->flags=0; h->seq=seq; h->insn_count=count; h->reserved=0; return sizeof(PfsInsnHdr);
}

#endif // PFS_INSN_H

