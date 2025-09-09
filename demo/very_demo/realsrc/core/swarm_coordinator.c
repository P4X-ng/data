/*
 * PacketFS Process Swarm Coordinator
 * Manages thousands of micro-executor processes for parallel instruction execution
 * Tests scaling from 1 to 10,000+ tiny processes on local machine
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <pthread.h>

/* Same PacketFS state structure as micro_executor.c */
typedef struct __attribute__((packed)) {
    uint8_t opcode;         
    uint8_t reg_target;     
    uint8_t reg_source;     
    uint8_t flags;          
    uint32_t immediate;     
    uint32_t registers[8];  
    uint32_t pc;           
    uint32_t result;       
    uint16_t checksum;     
    uint8_t padding[10];   
} PacketFSState;

/* Performance metrics */
typedef struct {
    uint32_t total_processes;
    uint32_t successful_executions;
    uint32_t failed_executions;
    uint64_t total_execution_time_ns;
    uint64_t min_execution_time_ns;
    uint64_t max_execution_time_ns;
    uint64_t spawn_overhead_ns;
    size_t memory_usage_kb;
} SwarmMetrics;

/* Process pool entry */
typedef struct {
    pid_t pid;
    int stdin_pipe[2];
    int stdout_pipe[2];
    PacketFSState instruction;
    PacketFSState result;
    uint32_t execution_time_ns;
    int status;
} ProcessEntry;

static SwarmMetrics g_metrics = {0};
static ProcessEntry* g_process_pool = NULL;
static volatile int g_shutdown = 0;

/* Signal handler for clean shutdown */
void signal_handler(int sig) {
    g_shutdown = 1;
}

/* Get current time in nanoseconds */
static uint64_t get_time_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

/* Spawn a single micro-executor process */
static int spawn_micro_executor(ProcessEntry* entry) {
    uint64_t spawn_start = get_time_ns();
    
    // Create pipes for communication
    if (pipe(entry->stdin_pipe) != 0 || pipe(entry->stdout_pipe) != 0) {
        perror("pipe");
        return -1;
    }
    
    // Fork the micro-executor
    entry->pid = fork();
    if (entry->pid == -1) {
        perror("fork");
        return -1;
    }
    
    if (entry->pid == 0) {
        // Child process: become micro-executor
        
        // Redirect stdin/stdout to pipes
        dup2(entry->stdin_pipe[0], STDIN_FILENO);
        dup2(entry->stdout_pipe[1], STDOUT_FILENO);
        
        // Close unused pipe ends
        close(entry->stdin_pipe[1]);
        close(entry->stdout_pipe[0]);
        close(entry->stdin_pipe[0]);
        close(entry->stdout_pipe[1]);
        
        // Execute micro-executor
        execl("./bin/micro_executor", "micro_executor", NULL);
        
        // If we get here, exec failed
        perror("execl");
        exit(1);
    } else {
        // Parent process: close unused pipe ends
        close(entry->stdin_pipe[0]);
        close(entry->stdout_pipe[1]);
        
        // Make pipes non-blocking
        fcntl(entry->stdin_pipe[1], F_SETFL, O_NONBLOCK);
        fcntl(entry->stdout_pipe[0], F_SETFL, O_NONBLOCK);
        
        g_metrics.spawn_overhead_ns += (get_time_ns() - spawn_start);
        return 0;
    }
}

/* Send instruction to micro-executor */
static int send_instruction(ProcessEntry* entry, PacketFSState* instruction) {
    ssize_t bytes_written = write(entry->stdin_pipe[1], instruction, sizeof(PacketFSState));
    if (bytes_written != sizeof(PacketFSState)) {
        return -1;
    }
    
    // Close stdin to signal instruction complete
    close(entry->stdin_pipe[1]);
    entry->stdin_pipe[1] = -1;
    
    return 0;
}

/* Read result from micro-executor */
static int read_result(ProcessEntry* entry) {
    ssize_t bytes_read = 0;
    uint8_t buffer[sizeof(PacketFSState) + sizeof(uint32_t)];
    
    // Try to read result + timing info
    bytes_read = read(entry->stdout_pipe[0], buffer, sizeof(buffer));
    if (bytes_read == sizeof(buffer)) {
        memcpy(&entry->result, buffer, sizeof(PacketFSState));
        memcpy(&entry->execution_time_ns, buffer + sizeof(PacketFSState), sizeof(uint32_t));
        return 0;
    }
    
    return -1; // Not ready yet or failed
}

/* Wait for micro-executor to complete */
static int wait_for_completion(ProcessEntry* entry) {
    int status;
    pid_t result = waitpid(entry->pid, &status, WNOHANG);
    
    if (result == entry->pid) {
        entry->status = status;
        return 0; // Process completed
    } else if (result == 0) {
        return 1; // Still running
    } else {
        return -1; // Error
    }
}

/* Execute a batch of instructions using process swarm */
static void execute_instruction_batch(PacketFSState* instructions, uint32_t count) {
    printf("🚀 Executing %u instructions using %u processes...\n", count, count);
    
    uint64_t batch_start = get_time_ns();
    
    // Allocate process pool
    g_process_pool = calloc(count, sizeof(ProcessEntry));
    if (!g_process_pool) {
        fprintf(stderr, "Failed to allocate process pool\n");
        return;
    }
    
    // Spawn all micro-executors
    uint32_t spawned = 0;
    for (uint32_t i = 0; i < count && !g_shutdown; i++) {
        g_process_pool[i].instruction = instructions[i];
        
        if (spawn_micro_executor(&g_process_pool[i]) == 0) {
            spawned++;
        } else {
            fprintf(stderr, "Failed to spawn process %u: %s\n", i, strerror(errno));
            g_metrics.failed_executions++;
        }
        
        // Brief pause to avoid overwhelming system
        if (i % 100 == 0 && i > 0) {
            usleep(1000); // 1ms pause every 100 processes
        }
    }
    
    printf("   ✅ Spawned %u processes\n", spawned);
    
    // Send instructions to all processes
    uint32_t instructions_sent = 0;
    for (uint32_t i = 0; i < spawned; i++) {
        if (send_instruction(&g_process_pool[i], &instructions[i]) == 0) {
            instructions_sent++;
        } else {
            g_metrics.failed_executions++;
        }
    }
    
    printf("   📤 Sent %u instructions\n", instructions_sent);
    
    // Wait for all processes to complete and collect results
    uint32_t completed = 0;
    uint32_t active = instructions_sent;
    
    while (active > 0 && !g_shutdown) {
        for (uint32_t i = 0; i < spawned; i++) {
            ProcessEntry* entry = &g_process_pool[i];
            
            // Skip if already completed
            if (entry->pid <= 0) continue;
            
            // Try to read result first
            if (read_result(entry) == 0) {
                // Result read successfully
                g_metrics.total_execution_time_ns += entry->execution_time_ns;
                
                if (entry->execution_time_ns < g_metrics.min_execution_time_ns || 
                    g_metrics.min_execution_time_ns == 0) {
                    g_metrics.min_execution_time_ns = entry->execution_time_ns;
                }
                
                if (entry->execution_time_ns > g_metrics.max_execution_time_ns) {
                    g_metrics.max_execution_time_ns = entry->execution_time_ns;
                }
            }
            
            // Check if process has completed
            int wait_result = wait_for_completion(entry);
            if (wait_result == 0) {
                // Process completed
                close(entry->stdout_pipe[0]);
                if (entry->stdin_pipe[1] != -1) {
                    close(entry->stdin_pipe[1]);
                }
                
                if (WIFEXITED(entry->status) && WEXITSTATUS(entry->status) == 0) {
                    g_metrics.successful_executions++;
                } else {
                    g_metrics.failed_executions++;
                }
                
                entry->pid = -1; // Mark as completed
                active--;
                completed++;
                
                if (completed % 1000 == 0) {
                    printf("   📊 Completed: %u/%u\n", completed, instructions_sent);
                }
            }
        }
        
        // Brief pause to avoid busy waiting
        usleep(100);
    }
    
    uint64_t batch_end = get_time_ns();
    uint64_t total_batch_time = batch_end - batch_start;
    
    printf("   🎯 Batch completed in %.2f ms\n", total_batch_time / 1000000.0);
    printf("   ✅ Successful: %u\n", g_metrics.successful_executions);
    printf("   ❌ Failed: %u\n", g_metrics.failed_executions);
    
    // Cleanup
    free(g_process_pool);
    g_process_pool = NULL;
}

/* Generate test instruction batch */
static PacketFSState* generate_test_instructions(uint32_t count) {
    PacketFSState* instructions = calloc(count, sizeof(PacketFSState));
    if (!instructions) return NULL;
    
    for (uint32_t i = 0; i < count; i++) {
        PacketFSState* inst = &instructions[i];
        
        // Generate different types of test instructions
        switch (i % 5) {
            case 0: // MOV instruction
                inst->opcode = 0x01; // OP_MOV
                inst->reg_target = i % 8;
                inst->immediate = i * 10;
                break;
                
            case 1: // ADD instruction  
                inst->opcode = 0x02; // OP_ADD
                inst->reg_target = i % 8;
                inst->reg_source = (i + 1) % 8;
                inst->registers[inst->reg_target] = i;
                inst->registers[inst->reg_source] = i * 2;
                break;
                
            case 2: // SUB instruction
                inst->opcode = 0x03; // OP_SUB
                inst->reg_target = i % 8;
                inst->reg_source = (i + 1) % 8;
                inst->registers[inst->reg_target] = i * 3;
                inst->registers[inst->reg_source] = i;
                break;
                
            case 3: // MUL instruction
                inst->opcode = 0x04; // OP_MUL
                inst->reg_target = i % 8;
                inst->reg_source = (i + 1) % 8;
                inst->registers[inst->reg_target] = (i % 100) + 1;
                inst->registers[inst->reg_source] = ((i + 1) % 10) + 1;
                break;
                
            case 4: // CMP instruction
                inst->opcode = 0x07; // OP_CMP
                inst->reg_target = i % 8;
                inst->reg_source = (i + 1) % 8;
                inst->registers[inst->reg_target] = i % 1000;
                inst->registers[inst->reg_source] = (i + 500) % 1000;
                break;
        }
        
        inst->pc = i;
    }
    
    return instructions;
}

/* Print performance metrics */
static void print_metrics(uint32_t instruction_count) {
    printf("\n🎯 PACKETFS PROCESS SWARM PERFORMANCE METRICS\n");
    printf("================================================================\n");
    printf("Total instructions:      %u\n", instruction_count);
    printf("Successful executions:   %u\n", g_metrics.successful_executions);
    printf("Failed executions:       %u\n", g_metrics.failed_executions);
    printf("Success rate:            %.1f%%\n", 
           (float)g_metrics.successful_executions / instruction_count * 100);
    
    if (g_metrics.successful_executions > 0) {
        uint64_t avg_exec_time = g_metrics.total_execution_time_ns / g_metrics.successful_executions;
        printf("\nExecution timing:\n");
        printf("  Average per instruction: %.2f μs\n", avg_exec_time / 1000.0);
        printf("  Minimum execution time:  %.2f μs\n", g_metrics.min_execution_time_ns / 1000.0);
        printf("  Maximum execution time:  %.2f μs\n", g_metrics.max_execution_time_ns / 1000.0);
        printf("  Total execution time:    %.2f ms\n", g_metrics.total_execution_time_ns / 1000000.0);
        printf("  Process spawn overhead:  %.2f ms\n", g_metrics.spawn_overhead_ns / 1000000.0);
    }
    
    // Calculate theoretical performance
    if (g_metrics.successful_executions > 0 && g_metrics.total_execution_time_ns > 0) {
        uint64_t instructions_per_second = (g_metrics.successful_executions * 1000000000ULL) / 
                                         g_metrics.total_execution_time_ns;
        printf("\nTheoretical performance:\n");
        printf("  Instructions per second: %lu\n", instructions_per_second);
        printf("  Equivalent CPU frequency: %.2f GHz\n", instructions_per_second / 1e9);
    }
    
    printf("================================================================\n");
}

/* Main swarm coordination function */
int main(int argc, char* argv[]) {
    printf("🌊💻⚡ PACKETFS PROCESS SWARM COORDINATOR 🚀💎\n\n");
    
    // Parse command line arguments
    uint32_t instruction_count = 1000; // Default
    if (argc > 1) {
        instruction_count = atoi(argv[1]);
        if (instruction_count == 0 || instruction_count > 50000) {
            fprintf(stderr, "Invalid instruction count (1-50000)\n");
            exit(1);
        }
    }
    
    printf("Target instruction count: %u\n", instruction_count);
    printf("Each instruction = 1 process = ultra-parallel execution\n\n");
    
    // Setup signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Initialize metrics
    g_metrics.total_processes = instruction_count;
    g_metrics.min_execution_time_ns = UINT64_MAX;
    
    // Generate test instructions
    printf("📝 Generating %u test instructions...\n", instruction_count);
    PacketFSState* instructions = generate_test_instructions(instruction_count);
    if (!instructions) {
        fprintf(stderr, "Failed to generate test instructions\n");
        exit(1);
    }
    
    // Execute instruction batch using process swarm
    execute_instruction_batch(instructions, instruction_count);
    
    // Print final metrics
    print_metrics(instruction_count);
    
    // Cleanup
    free(instructions);
    
    printf("\n💎 PacketFS Process Swarm test complete!\n");
    printf("🚀 Ready to scale to network deployment!\n");
    
    return 0;
}
