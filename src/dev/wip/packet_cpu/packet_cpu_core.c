/*
 * 🔥💀 PACKET CPU CORE IMPLEMENTATION 💀🔥
 * 
 * THE REVOLUTION BEGINS HERE!
 * NO MORE TRADITIONAL CPUS - WE ARE THE CPU!
 * PACKETS = INSTRUCTIONS, NETWORKING = EXECUTION PIPELINE
 */

#include "packet_cpu.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>
#include <errno.h>

// 🚀 PACKET CPU CORE CREATION (BIRTH OF A PACKET CPU!)
packet_cpu_core_t* packet_cpu_core_create(uint32_t core_id, void* shared_memory) {
    packet_cpu_core_t* core = malloc(sizeof(packet_cpu_core_t));
    if (!core) {
        PACKET_CPU_ERROR("Failed to allocate packet CPU core %u", core_id);
        return NULL;
    }

    // Initialize packet CPU state (OUR REGISTERS!)
    memset(&core->state, 0, sizeof(packet_cpu_state_t));
    core->state.core_id = core_id;
    core->state.active = true;
    core->state.memory_base = shared_memory;
    core->state.memory_size = PACKET_CPU_MEMORY_ARENA_SIZE;
    core->state.memory_offset = 0;
    
    // Initialize packet registers (FUCK x86 REGISTERS!)
    core->state.reg_a = 0;
    core->state.reg_b = 0;
    core->state.reg_c = 0;
    core->state.reg_d = 0;
    core->state.reg_sp = PACKET_CPU_MEMORY_ARENA_SIZE - 1024; // Stack at end of arena
    core->state.reg_pc = 0;
    core->state.reg_flags = 0;
    
    // Set up packet network interface
    memset(&core->network, 0, sizeof(packet_network_t));
    core->network.socket_fd = -1;
    core->network.port = PACKET_CPU_NETWORK_PORT + core_id; // Each core gets unique port
    
    // Initialize shared memory pointer
    core->shared_mem = shared_memory;
    core->terminated = false;
    core->term_sig = 0;
    
    PACKET_CPU_LOG("🎯 Created Packet CPU Core #%u (Port: %u)", core_id, core->network.port);
    return core;
}

// 💀 PACKET CPU CORE DESTRUCTION (CLEAN PACKET DEATH!)
void packet_cpu_core_destroy(packet_cpu_core_t* core) {
    if (!core) return;
    
    PACKET_CPU_LOG("💀 Destroying Packet CPU Core #%u", core->state.core_id);
    
    // Clean up network interface
    if (core->network.socket_fd >= 0) {
        close(core->network.socket_fd);
    }
    
    // Mark as inactive (NO SYSCALL EXIT!)
    core->state.active = false;
    core->terminated = true;
    core->term_sig = PACKET_CPU_TERMINATION_SIG;
    
    free(core);
}

// 🎯 PACKET INSTRUCTION EXECUTION (THE REAL CPU!)
int packet_cpu_core_execute(packet_cpu_core_t* core, packet_instruction_t* instruction) {
    if (!core || !instruction) {
        return -1;
    }
    
    if (!core->state.active) {
        return -1; // Core is not active
    }
    
    // Copy instruction to core
    memcpy(&core->instruction, instruction, sizeof(packet_instruction_t));
    core->state.cycles++;
    
    PACKET_CPU_LOG("🔥 Core #%u executing opcode 0x%02X", 
                   core->state.core_id, instruction->opcode);
    
    // Execute packet opcode (FUCK TRADITIONAL x86 INSTRUCTION DECODE!)
    switch (instruction->opcode) {
        case PACKET_OP_NOP:
            // No operation - just burn a cycle
            break;
            
        case PACKET_OP_LOAD:
            // Load from memory arena to register A
            if (packet_memory_read(core, instruction->operand1, 
                                 &core->state.reg_a, sizeof(uint64_t)) == 0) {
                PACKET_CPU_LOG("📥 LOAD: reg_a = 0x%lx from offset 0x%x", 
                              core->state.reg_a, instruction->operand1);
            }
            break;
            
        case PACKET_OP_STORE:
            // Store register A to memory arena
            if (packet_memory_write(core, instruction->operand1, 
                                  &core->state.reg_a, sizeof(uint64_t)) == 0) {
                PACKET_CPU_LOG("📤 STORE: 0x%lx to offset 0x%x", 
                              core->state.reg_a, instruction->operand1);
            }
            break;
            
        case PACKET_OP_ADD:
            // Addition: reg_a = reg_a + operand1
            core->state.reg_a += instruction->operand1;
            PACKET_CPU_LOG("➕ ADD: reg_a = 0x%lx", core->state.reg_a);
            break;
            
        case PACKET_OP_SUB:
            // Subtraction: reg_a = reg_a - operand1
            core->state.reg_a -= instruction->operand1;
            PACKET_CPU_LOG("➖ SUB: reg_a = 0x%lx", core->state.reg_a);
            break;
            
        case PACKET_OP_MUL:
            // Multiplication: reg_a = reg_a * operand1
            core->state.reg_a *= instruction->operand1;
            PACKET_CPU_LOG("✖️ MUL: reg_a = 0x%lx", core->state.reg_a);
            break;
            
        case PACKET_OP_DIV:
            // Division: reg_a = reg_a / operand1 (avoid division by zero)
            if (instruction->operand1 != 0) {
                core->state.reg_a /= instruction->operand1;
                PACKET_CPU_LOG("➗ DIV: reg_a = 0x%lx", core->state.reg_a);
            } else {
                PACKET_CPU_ERROR("Division by zero in core #%u", core->state.core_id);
                return -1;
            }
            break;
            
        case PACKET_OP_JUMP:
            // Jump: set program counter to operand1
            core->state.reg_pc = instruction->operand1;
            PACKET_CPU_LOG("🦘 JUMP: pc = 0x%x", instruction->operand1);
            break;
            
        case PACKET_OP_CMP:
            // Compare: set flags based on reg_a vs operand1
            if (core->state.reg_a == instruction->operand1) {
                core->state.reg_flags |= 0x01; // Zero flag
            } else {
                core->state.reg_flags &= ~0x01;
            }
            if (core->state.reg_a > instruction->operand1) {
                core->state.reg_flags |= 0x02; // Greater flag
            } else {
                core->state.reg_flags &= ~0x02;
            }
            PACKET_CPU_LOG("🔍 CMP: flags = 0x%lx", core->state.reg_flags);
            break;
            
        case PACKET_OP_BRANCH:
            // Conditional branch based on flags
            if ((instruction->operand2 & core->state.reg_flags) != 0) {
                core->state.reg_pc = instruction->operand1;
                PACKET_CPU_LOG("🌿 BRANCH: taken, pc = 0x%x", instruction->operand1);
            } else {
                PACKET_CPU_LOG("🌿 BRANCH: not taken");
            }
            break;
            
        case PACKET_OP_SPAWN:
            // Spawn new packet execution (PACKET MULTIPLICATION!)
            PACKET_CPU_LOG("🐣 SPAWN: Creating new packet execution");
            // TODO: Implement packet spawning mechanism
            break;
            
        case PACKET_OP_MERGE:
            // Merge packet results (PACKET FUSION!)
            PACKET_CPU_LOG("🤝 MERGE: Merging packet results");
            // TODO: Implement packet merging
            break;
            
        case PACKET_OP_SPLIT:
            // Split packet into multiple (PACKET MITOSIS!)
            PACKET_CPU_LOG("✂️ SPLIT: Splitting packet execution");
            // TODO: Implement packet splitting
            break;
            
        case PACKET_OP_FILTER:
            // Filter packets (PACKET FIREWALL!)
            PACKET_CPU_LOG("🚫 FILTER: Filtering packets");
            // TODO: Implement packet filtering
            break;
            
        case PACKET_OP_ROUTE:
            // Route to different execution path (PACKET ROUTING!)
            PACKET_CPU_LOG("🛤️ ROUTE: Routing packet execution");
            // TODO: Implement packet routing
            break;
            
        case PACKET_OP_FS_READ:
            // Read from packet filesystem
            PACKET_CPU_LOG("📖 FS_READ: Reading from PacketFS");
            // TODO: Implement PacketFS read
            break;
            
        case PACKET_OP_FS_WRITE:
            // Write to packet filesystem
            PACKET_CPU_LOG("📝 FS_WRITE: Writing to PacketFS");
            // TODO: Implement PacketFS write
            break;
            
        case PACKET_OP_FS_EXEC:
            // Execute packet file
            PACKET_CPU_LOG("🏃 FS_EXEC: Executing PacketFS file");
            // TODO: Implement PacketFS execution
            break;
            
        case PACKET_OP_HALT:
            // Halt packet execution (NO SYSCALL EXIT!)
            PACKET_CPU_LOG("🛑 HALT: Core #%u terminated with signature 0x%08x", 
                          core->state.core_id, instruction->operand1);
            core->terminated = true;
            core->term_sig = instruction->operand1;
            core->state.active = false;
            
            // Verify termination signature
            if (PACKET_CPU_IS_TERMINATED(instruction->operand1)) {
                PACKET_CPU_LOG("✅ Valid termination signature received");
                return 0;
            } else {
                PACKET_CPU_ERROR("Invalid termination signature: 0x%08x", instruction->operand1);
                return -1;
            }
            break;
            
        default:
            PACKET_CPU_ERROR("Unknown opcode 0x%02X in core #%u", 
                           instruction->opcode, core->state.core_id);
            return -1;
    }
    
    // Update program counter (unless it was explicitly modified)
    if (instruction->opcode != PACKET_OP_JUMP && instruction->opcode != PACKET_OP_BRANCH) {
        core->state.reg_pc++;
    }
    
    return 0;
}

// 🎯 PACKET INSTRUCTION CREATION
packet_instruction_t packet_cpu_instruction_create(packet_opcode_t opcode, 
                                                  uint32_t op1, uint32_t op2, uint32_t op3) {
    packet_instruction_t instruction;
    instruction.opcode = opcode;
    instruction.operand1 = op1;
    instruction.operand2 = op2;
    instruction.operand3 = op3;
    
    // Set timestamp (nanosecond precision)
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    instruction.timestamp = (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
    
    return instruction;
}

// 💀 CHECK IF INSTRUCTION IS TERMINATION
bool packet_cpu_instruction_is_termination(packet_instruction_t* instruction) {
    if (!instruction) return false;
    
    return (instruction->opcode == PACKET_OP_HALT && 
            PACKET_CPU_IS_TERMINATED(instruction->operand1));
}

// 📄 PRINT PACKET INSTRUCTION
void packet_cpu_instruction_print(packet_instruction_t* instruction) {
    if (!instruction) return;
    
    printf("🔥 Packet Instruction:\n");
    printf("   Opcode: 0x%02X\n", instruction->opcode);
    printf("   Operand1: 0x%08X\n", instruction->operand1);
    printf("   Operand2: 0x%08X\n", instruction->operand2);
    printf("   Operand3: 0x%08X\n", instruction->operand3);
    printf("   Timestamp: %lu ns\n", instruction->timestamp);
}

// 🧠 MEMORY ARENA FUNCTIONS (PACKETS AS MEMORY MANAGEMENT!)

void* packet_memory_arena_create(size_t size) {
    void* arena = mmap(NULL, size, PROT_READ | PROT_WRITE, 
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (arena == MAP_FAILED) {
        PACKET_CPU_ERROR("Failed to create memory arena: %s", strerror(errno));
        return NULL;
    }
    
    PACKET_CPU_LOG("🧠 Created memory arena: %zu bytes at %p", size, arena);
    
    // Initialize arena with packet signature
    uint32_t* sig_ptr = (uint32_t*)arena;
    *sig_ptr = 0xFEEDFACE; // PacketFS memory signature
    
    return arena;
}

void packet_memory_arena_destroy(void* arena) {
    if (!arena) return;
    
    PACKET_CPU_LOG("💀 Destroying memory arena at %p", arena);
    munmap(arena, PACKET_CPU_MEMORY_ARENA_SIZE);
}

int packet_memory_read(packet_cpu_core_t* core, uint64_t offset, void* data, size_t size) {
    if (!core || !data || !core->state.memory_base) {
        return -1;
    }
    
    if (offset + size > core->state.memory_size) {
        PACKET_CPU_ERROR("Memory read out of bounds: offset=%lu, size=%zu", offset, size);
        return -1;
    }
    
    void* src = (uint8_t*)core->state.memory_base + offset;
    memcpy(data, src, size);
    
    return 0;
}

int packet_memory_write(packet_cpu_core_t* core, uint64_t offset, const void* data, size_t size) {
    if (!core || !data || !core->state.memory_base) {
        return -1;
    }
    
    if (offset + size > core->state.memory_size) {
        PACKET_CPU_ERROR("Memory write out of bounds: offset=%lu, size=%zu", offset, size);
        return -1;
    }
    
    void* dest = (uint8_t*)core->state.memory_base + offset;
    memcpy(dest, data, size);
    
    return 0;
}
