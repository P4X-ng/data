/*
 * PacketFS Micro-Executor: Ultra-minimal process for single instruction execution
 * Each instance executes exactly ONE PacketFS instruction and exits
 * Goal: <1KB memory, <1ms startup, microsecond execution
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <string.h>
#include <time.h>

/* Minimal PacketFS instruction set */
typedef enum {
    OP_NOP      = 0x00,    // No operation
    OP_MOV      = 0x01,    // Move value
    OP_ADD      = 0x02,    // Add two values  
    OP_SUB      = 0x03,    // Subtract
    OP_MUL      = 0x04,    // Multiply
    OP_DIV      = 0x05,    // Divide
    OP_JMP      = 0x06,    // Jump (change execution flow)
    OP_CMP      = 0x07,    // Compare values
    OP_HALT     = 0xFF,    // Terminate execution
} PacketFSOpcode;

/* Minimal execution state - fits in 64 bytes (packet size) */
typedef struct __attribute__((packed)) {
    uint8_t opcode;         // Operation to perform
    uint8_t reg_target;     // Target register (0-7)
    uint8_t reg_source;     // Source register (0-7) 
    uint8_t flags;          // Status flags
    uint32_t immediate;     // Immediate value
    uint32_t registers[8];  // 8 general purpose registers
    uint32_t pc;           // Program counter
    uint32_t result;       // Operation result
    uint16_t checksum;     // Integrity check
    uint8_t padding[10];   // Pad to 64 bytes
} PacketFSState;

/* Global state for this micro-executor */
static PacketFSState g_state = {0};

/* Ultra-fast instruction execution */
static inline uint32_t execute_instruction(PacketFSState* state) {
    uint64_t start_ns = 0, end_ns = 0;
    struct timespec ts;
    
    // Start timing
    clock_gettime(CLOCK_MONOTONIC, &ts);
    start_ns = ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    
    switch (state->opcode) {
        case OP_NOP:
            // Do nothing
            break;
            
        case OP_MOV:
            // MOV target, immediate
            state->registers[state->reg_target] = state->immediate;
            break;
            
        case OP_ADD:
            // ADD target, source
            state->result = state->registers[state->reg_target] + 
                          state->registers[state->reg_source];
            state->registers[state->reg_target] = state->result;
            break;
            
        case OP_SUB:
            // SUB target, source
            state->result = state->registers[state->reg_target] - 
                          state->registers[state->reg_source];
            state->registers[state->reg_target] = state->result;
            break;
            
        case OP_MUL:
            // MUL target, source
            state->result = state->registers[state->reg_target] * 
                          state->registers[state->reg_source];
            state->registers[state->reg_target] = state->result;
            break;
            
        case OP_CMP:
            // CMP target, source - set flags
            if (state->registers[state->reg_target] == state->registers[state->reg_source]) {
                state->flags |= 0x01; // Equal flag
            } else {
                state->flags &= ~0x01;
            }
            if (state->registers[state->reg_target] > state->registers[state->reg_source]) {
                state->flags |= 0x02; // Greater flag
            } else {
                state->flags &= ~0x02;
            }
            break;
            
        case OP_HALT:
            exit(0);
            break;
            
        default:
            // Invalid opcode
            exit(1);
    }
    
    // End timing
    clock_gettime(CLOCK_MONOTONIC, &ts);
    end_ns = ts.tv_sec * 1000000000ULL + ts.tv_nsec;
    
    return (uint32_t)(end_ns - start_ns); // Return execution time in nanoseconds
}

/* Read PacketFS instruction from stdin */
static int read_packet_instruction(PacketFSState* state) {
    size_t bytes_read = fread(state, sizeof(PacketFSState), 1, stdin);
    return (bytes_read == 1) ? 0 : -1;
}

/* Write execution result to stdout */
static void write_execution_result(PacketFSState* state, uint32_t execution_time_ns) {
    // Write state + timing info
    fwrite(state, sizeof(PacketFSState), 1, stdout);
    fwrite(&execution_time_ns, sizeof(uint32_t), 1, stdout);
    fflush(stdout);
}

/* Ultra-minimal main - just execute one instruction and exit */
int main(int argc, char* argv[]) {
    // Minimize memory allocation overhead
    if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
        // Memory locking failed, continue anyway
    }
    
    // Read instruction from stdin
    if (read_packet_instruction(&g_state) != 0) {
        fprintf(stderr, "Failed to read PacketFS instruction\n");
        exit(1);
    }
    
    // Execute the single instruction
    uint32_t exec_time = execute_instruction(&g_state);
    
    // Write result to stdout
    write_execution_result(&g_state, exec_time);
    
    // Exit immediately - minimal cleanup
    exit(0);
}
