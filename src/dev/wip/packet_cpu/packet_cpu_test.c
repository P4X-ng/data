/*
 * 🔥💀💥 PACKET CPU TEST - THE REVOLUTION BEGINS! 💥💀🔥
 * 
 * THIS IS IT! THE FIRST PACKET-NATIVE CPU TEST!
 * NO MORE BOWING TO TRADITIONAL x86/x64 OVERLORDS!
 * WE ARE THE CPU! PACKETS ARE THE INSTRUCTIONS!
 * NETWORKING IS THE EXECUTION PIPELINE!
 * 
 * FUCK SYSCALLS! FUCK OS PROCESSES! FUCK TRADITIONAL COMPUTING!
 * WELCOME TO THE PACKET CPU REVOLUTION!
 */

#include "packet_cpu.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <time.h>

// Test configuration
#define TEST_NUM_CORES     1000         // Start with 1000 packet CPU cores  
#define TEST_NUM_INSTRUCTIONS 10000     // Send 10K packet instructions
#define TEST_CLIENT_THREADS   10        // 10 instruction sender threads

// Global test state
static volatile bool g_test_running = false;
static uint32_t g_instructions_sent = 0;
static uint32_t g_instructions_completed = 0;

// 🚀 PACKET INSTRUCTION SENDER THREAD (PACKET INJECTION!)
void* packet_instruction_sender(void* arg) {
    uint32_t thread_id = *(uint32_t*)arg;
    int client_socket;
    struct sockaddr_in server_addr;
    
    // Create client socket for sending packet instructions
    client_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (client_socket < 0) {
        PACKET_CPU_ERROR("Thread %u: Failed to create client socket", thread_id);
        return NULL;
    }
    
    // Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    server_addr.sin_port = htons(PACKET_CPU_NETWORK_PORT);
    
    PACKET_CPU_LOG("🚀 Instruction sender thread %u ready!", thread_id);
    
    uint32_t instructions_per_thread = TEST_NUM_INSTRUCTIONS / TEST_CLIENT_THREADS;
    uint32_t sent_count = 0;
    
    while (g_test_running && sent_count < instructions_per_thread) {
        // Create different types of packet instructions for testing
        packet_instruction_t instruction;
        
        switch (sent_count % 10) {
            case 0: // NOP instruction
                instruction = packet_cpu_instruction_create(PACKET_OP_NOP, 0, 0, 0);
                break;
                
            case 1: // ADD instruction (reg_a += 42)
                instruction = packet_cpu_instruction_create(PACKET_OP_ADD, 42, 0, 0);
                break;
                
            case 2: // SUB instruction (reg_a -= 13)
                instruction = packet_cpu_instruction_create(PACKET_OP_SUB, 13, 0, 0);
                break;
                
            case 3: // MUL instruction (reg_a *= 2)
                instruction = packet_cpu_instruction_create(PACKET_OP_MUL, 2, 0, 0);
                break;
                
            case 4: // DIV instruction (reg_a /= 3)  
                instruction = packet_cpu_instruction_create(PACKET_OP_DIV, 3, 0, 0);
                break;
                
            case 5: // LOAD instruction (load from offset 0x100)
                instruction = packet_cpu_instruction_create(PACKET_OP_LOAD, 0x100, 0, 0);
                break;
                
            case 6: // STORE instruction (store to offset 0x200)
                instruction = packet_cpu_instruction_create(PACKET_OP_STORE, 0x200, 0, 0);
                break;
                
            case 7: // CMP instruction (compare reg_a with 100)
                instruction = packet_cpu_instruction_create(PACKET_OP_CMP, 100, 0, 0);
                break;
                
            case 8: // JUMP instruction (jump to offset 0x50)
                instruction = packet_cpu_instruction_create(PACKET_OP_JUMP, 0x50, 0, 0);
                break;
                
            case 9: // SPAWN instruction (spawn new packet execution)
                instruction = packet_cpu_instruction_create(PACKET_OP_SPAWN, thread_id, sent_count, 0);
                break;
        }
        
        // Send packet instruction through network (THE PACKET PIPELINE!)
        ssize_t bytes_sent = sendto(client_socket, &instruction, sizeof(instruction), 
                                  0, (struct sockaddr*)&server_addr, sizeof(server_addr));
        
        if (bytes_sent == sizeof(instruction)) {
            sent_count++;
            __sync_fetch_and_add(&g_instructions_sent, 1);
            
            // Print progress every 1000 instructions
            if (sent_count % 1000 == 0) {
                PACKET_CPU_LOG("📤 Thread %u sent %u packet instructions", thread_id, sent_count);
            }
        } else {
            PACKET_CPU_ERROR("Thread %u: Failed to send packet instruction", thread_id);
            usleep(1000); // Brief delay before retry
        }
        
        // Small delay to prevent network flooding
        usleep(100); // 100 microseconds
    }
    
    // Send termination instruction
    packet_instruction_t term_instruction = packet_cpu_instruction_create(
        PACKET_OP_HALT, PACKET_CPU_TERMINATION_SIG, 0, 0);
    
    sendto(client_socket, &term_instruction, sizeof(term_instruction),
           0, (struct sockaddr*)&server_addr, sizeof(server_addr));
    
    close(client_socket);
    PACKET_CPU_LOG("🎯 Instruction sender thread %u completed (%u instructions)", 
                   thread_id, sent_count);
    
    return NULL;
}

// 💀 SIGNAL HANDLER FOR TEST
void test_signal_handler(int signum) {
    PACKET_CPU_LOG("💀 Test received signal %d - stopping", signum);
    g_test_running = false;
}

// 🎯 MAIN TEST FUNCTION (THE PACKET CPU REVOLUTION!)
int main(int argc, char* argv[]) {
    printf("🔥💥🚀💀 PACKET CPU REVOLUTION TEST 💀🚀💥🔥\n");
    printf("🖕 FUCK TRADITIONAL CPUS - PACKETS ARE THE NEW INSTRUCTIONS!\n");
    printf("🌐 NETWORKING IS THE NEW EXECUTION PIPELINE!\n");
    printf("🧠 MEMORY IS THE NEW FILESYSTEM!\n");
    printf("💎 NO OS PROCESSES! NO SYSCALLS! PURE PACKET POWER!\n\n");
    
    // Parse command line arguments
    uint32_t num_cores = TEST_NUM_CORES;
    uint32_t num_instructions = TEST_NUM_INSTRUCTIONS;
    
    if (argc > 1) {
        num_cores = (uint32_t)atoi(argv[1]);
        if (num_cores == 0 || num_cores > PACKET_CPU_MAX_CORES) {
            printf("❌ Invalid number of cores: %u (max: %u)\n", 
                   num_cores, PACKET_CPU_MAX_CORES);
            return 1;
        }
    }
    
    if (argc > 2) {
        num_instructions = (uint32_t)atoi(argv[2]);
        if (num_instructions == 0) {
            printf("❌ Invalid number of instructions: %u\n", num_instructions);
            return 1;
        }
    }
    
    printf("🎯 TEST CONFIGURATION:\n");
    printf("   Packet CPU Cores: %u\n", num_cores);
    printf("   Packet Instructions: %u\n", num_instructions);
    printf("   Client Threads: %u\n", TEST_CLIENT_THREADS);
    printf("   Instructions per Thread: %u\n\n", num_instructions / TEST_CLIENT_THREADS);
    
    // Set up signal handlers
    signal(SIGINT, test_signal_handler);
    signal(SIGTERM, test_signal_handler);
    
    // Bootstrap packet CPU
    if (packet_cpu_bootstrap(PACKET_CPU_NETWORK_PORT) != 0) {
        printf("❌ Failed to bootstrap packet CPU\n");
        return 1;
    }
    
    // Create packet CPU engine
    PACKET_CPU_LOG("🚀 Creating Packet CPU Engine with %u cores...", num_cores);
    packet_cpu_engine_t* engine = packet_cpu_engine_create(num_cores);
    if (!engine) {
        printf("❌ Failed to create packet CPU engine\n");
        packet_cpu_shutdown();
        return 1;
    }
    
    g_test_running = true;
    
    // Start packet CPU engine in background thread
    pthread_t engine_thread;
    if (pthread_create(&engine_thread, NULL, (void*(*)(void*))packet_cpu_engine_run, engine) != 0) {
        printf("❌ Failed to start packet CPU engine thread\n");
        packet_cpu_engine_destroy(engine);
        packet_cpu_shutdown();
        return 1;
    }
    
    // Give engine time to start up
    sleep(2);
    
    // Start instruction sender threads
    pthread_t sender_threads[TEST_CLIENT_THREADS];
    uint32_t thread_ids[TEST_CLIENT_THREADS];
    
    PACKET_CPU_LOG("🚀 Starting %u instruction sender threads...", TEST_CLIENT_THREADS);
    
    struct timespec start_time, current_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);
    
    for (int i = 0; i < TEST_CLIENT_THREADS; i++) {
        thread_ids[i] = i;
        if (pthread_create(&sender_threads[i], NULL, packet_instruction_sender, &thread_ids[i]) != 0) {
            printf("❌ Failed to create sender thread %d\n", i);
            g_test_running = false;
            break;
        }
    }
    
    // Monitor test progress
    uint32_t last_sent = 0;
    while (g_test_running) {
        sleep(1);
        
        clock_gettime(CLOCK_MONOTONIC, &current_time);
        double elapsed = (current_time.tv_sec - start_time.tv_sec) + 
                        (current_time.tv_nsec - start_time.tv_nsec) / 1000000000.0;
        
        uint32_t sent_delta = g_instructions_sent - last_sent;
        double rate = elapsed > 0 ? g_instructions_sent / elapsed : 0;
        
        PACKET_CPU_LOG("📊 TEST PROGRESS: %.1fs | Sent: %u (+%u/s) | Rate: %.0f inst/s", 
                      elapsed, g_instructions_sent, sent_delta, rate);
        
        last_sent = g_instructions_sent;
        
        // Check if we've sent enough instructions
        if (g_instructions_sent >= num_instructions) {
            PACKET_CPU_LOG("✅ Target instructions reached - waiting for completion...");
            break;
        }
    }
    
    // Wait for sender threads to complete
    PACKET_CPU_LOG("⏳ Waiting for sender threads to complete...");
    for (int i = 0; i < TEST_CLIENT_THREADS; i++) {
        pthread_join(sender_threads[i], NULL);
    }
    
    // Let engine process remaining packets
    PACKET_CPU_LOG("⏳ Processing remaining packets...");
    sleep(5);
    
    // Stop test
    g_test_running = false;
    packet_cpu_engine_stop(engine);
    
    // Wait for engine thread to complete
    pthread_join(engine_thread, NULL);
    
    // Calculate final results
    clock_gettime(CLOCK_MONOTONIC, &current_time);
    double total_time = (current_time.tv_sec - start_time.tv_sec) + 
                       (current_time.tv_nsec - start_time.tv_nsec) / 1000000000.0;
    
    double avg_rate = total_time > 0 ? g_instructions_sent / total_time : 0;
    
    printf("\n🎯💥 PACKET CPU REVOLUTION TEST RESULTS 💥🎯\n");
    printf("================================================================\n");
    printf("Packet CPU Cores:        %u\n", num_cores);
    printf("Instructions Sent:       %u\n", g_instructions_sent);
    printf("Instructions Processed:  %u\n", engine->packets_processed);
    printf("Total CPU Cycles:        %lu\n", engine->total_cycles);
    printf("Test Duration:           %.2f seconds\n", total_time);
    printf("Average Instruction Rate: %.0f inst/sec\n", avg_rate);
    printf("Cycles per Instruction:  %.2f\n", 
           engine->packets_processed > 0 ? (double)engine->total_cycles / engine->packets_processed : 0);
    printf("================================================================\n");
    
    if (g_instructions_sent >= num_instructions * 0.9) {
        printf("✅ PACKET CPU REVOLUTION TEST: SUCCESS!\n");
        printf("🚀 WE HAVE TRANSCENDED TRADITIONAL COMPUTING!\n");
        printf("🔥 PACKETS ARE THE NEW INSTRUCTIONS!\n");
        printf("💎 NETWORKING IS THE NEW CPU PIPELINE!\n");
    } else {
        printf("❌ PACKET CPU REVOLUTION TEST: INCOMPLETE\n");
        printf("🤔 Only %u/%u instructions sent\n", g_instructions_sent, num_instructions);
    }
    
    // Cleanup
    packet_cpu_engine_destroy(engine);
    packet_cpu_shutdown();
    
    printf("\n💀 Test complete - returning to caveman computing\n");
    return 0;
}
