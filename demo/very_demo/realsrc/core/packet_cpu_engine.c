/*
 * 🔥💀 PACKET CPU ENGINE - NETWORK EXECUTION PIPELINE 💀🔥
 * 
 * THIS IS WHERE THE MAGIC HAPPENS!
 * NETWORKING STACK = EXECUTION PIPELINE
 * PACKETS = INSTRUCTIONS FLOWING THROUGH THE NETWORK
 * NO TRADITIONAL OS BULLSHIT!
 */

#include "packet_cpu.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <sys/time.h>
#include <errno.h>

// Global engine instance (there can be only one!)
static packet_cpu_engine_t* g_engine = NULL;
static volatile bool g_engine_running = false;

// 🚀 PACKET CPU ENGINE CREATION (BIRTH OF PACKET CPU REVOLUTION!)
packet_cpu_engine_t* packet_cpu_engine_create(uint32_t num_cores) {
    if (num_cores > PACKET_CPU_MAX_CORES) {
        PACKET_CPU_ERROR("Requested %u cores exceeds maximum of %u", 
                        num_cores, PACKET_CPU_MAX_CORES);
        return NULL;
    }
    
    packet_cpu_engine_t* engine = malloc(sizeof(packet_cpu_engine_t));
    if (!engine) {
        PACKET_CPU_ERROR("Failed to allocate packet CPU engine");
        return NULL;
    }
    
    // Initialize engine structure
    memset(engine, 0, sizeof(packet_cpu_engine_t));
    engine->num_cores = num_cores;
    engine->running = false;
    engine->total_cycles = 0;
    engine->packets_processed = 0;
    
    // Create shared memory arena (THE PACKET MEMORY UNIVERSE!)
    engine->memory_size = PACKET_CPU_MEMORY_ARENA_SIZE;
    engine->shared_memory = packet_memory_arena_create(engine->memory_size);
    if (!engine->shared_memory) {
        PACKET_CPU_ERROR("Failed to create shared memory arena");
        free(engine);
        return NULL;
    }
    
    // Allocate packet CPU cores array
    engine->cores = malloc(sizeof(packet_cpu_core_t*) * num_cores);
    if (!engine->cores) {
        PACKET_CPU_ERROR("Failed to allocate cores array");
        packet_memory_arena_destroy(engine->shared_memory);
        free(engine);
        return NULL;
    }
    
    // Create packet CPU cores (THE PACKET CPU ARMY!)
    PACKET_CPU_LOG("🎯 Creating %u Packet CPU cores...", num_cores);
    for (uint32_t i = 0; i < num_cores; i++) {
        engine->cores[i] = packet_cpu_core_create(i, engine->shared_memory);
        if (!engine->cores[i]) {
            PACKET_CPU_ERROR("Failed to create packet CPU core #%u", i);
            // Clean up created cores
            for (uint32_t j = 0; j < i; j++) {
                packet_cpu_core_destroy(engine->cores[j]);
            }
            free(engine->cores);
            packet_memory_arena_destroy(engine->shared_memory);
            free(engine);
            return NULL;
        }
    }
    
    PACKET_CPU_LOG("🚀 Packet CPU Engine created with %u cores!", num_cores);
    PACKET_CPU_LOG("💎 Shared memory arena: %zu bytes", engine->memory_size);
    
    return engine;
}

// 💀 PACKET CPU ENGINE DESTRUCTION (CLEAN PACKET DEATH!)
void packet_cpu_engine_destroy(packet_cpu_engine_t* engine) {
    if (!engine) return;
    
    PACKET_CPU_LOG("💀 Destroying Packet CPU Engine...");
    
    // Stop the engine if running
    if (engine->running) {
        packet_cpu_engine_stop(engine);
    }
    
    // Destroy all packet CPU cores
    if (engine->cores) {
        for (uint32_t i = 0; i < engine->num_cores; i++) {
            if (engine->cores[i]) {
                packet_cpu_core_destroy(engine->cores[i]);
            }
        }
        free(engine->cores);
    }
    
    // Destroy shared memory arena
    if (engine->shared_memory) {
        packet_memory_arena_destroy(engine->shared_memory);
    }
    
    PACKET_CPU_LOG("🎯 Engine destroyed. Total cycles: %lu, Packets: %u", 
                   engine->total_cycles, engine->packets_processed);
    
    free(engine);
}

// 🌐 NETWORK PACKET RECEIVER THREAD (PACKET INSTRUCTION PIPELINE!)
void* packet_cpu_network_receiver(void* arg) {
    packet_cpu_engine_t* engine = (packet_cpu_engine_t*)arg;
    int server_socket;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);
    
    // Create server socket for receiving packet instructions
    server_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (server_socket < 0) {
        PACKET_CPU_ERROR("Failed to create server socket: %s", strerror(errno));
        return NULL;
    }
    
    // Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PACKET_CPU_NETWORK_PORT);
    
    // Bind socket
    if (bind(server_socket, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        PACKET_CPU_ERROR("Failed to bind socket: %s", strerror(errno));
        close(server_socket);
        return NULL;
    }
    
    PACKET_CPU_LOG("🌐 Network receiver listening on port %u", PACKET_CPU_NETWORK_PORT);
    
    // Packet instruction receive loop (THE PACKET PIPELINE!)
    while (engine->running) {
        packet_instruction_t instruction;
        
        // Receive packet instruction from network
        ssize_t bytes_recv = recvfrom(server_socket, &instruction, sizeof(instruction),
                                    0, (struct sockaddr*)&client_addr, &client_len);
        
        if (bytes_recv == sizeof(instruction)) {
            // Find available packet CPU core
            packet_cpu_core_t* available_core = NULL;
            for (uint32_t i = 0; i < engine->num_cores; i++) {
                if (engine->cores[i] && engine->cores[i]->state.active && 
                    !engine->cores[i]->terminated) {
                    available_core = engine->cores[i];
                    break;
                }
            }
            
            if (available_core) {
                // Execute packet instruction on available core
                int result = packet_cpu_core_execute(available_core, &instruction);
                if (result == 0) {
                    engine->packets_processed++;
                    engine->total_cycles += available_core->state.cycles;
                    
                    // Check for termination instruction
                    if (packet_cpu_instruction_is_termination(&instruction)) {
                        PACKET_CPU_LOG("🛑 Termination instruction received");
                        break;
                    }
                } else {
                    PACKET_CPU_ERROR("Failed to execute instruction on core #%u", 
                                   available_core->state.core_id);
                }
            } else {
                PACKET_CPU_ERROR("No available cores for packet execution!");
            }
        } else if (bytes_recv < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
            PACKET_CPU_ERROR("Error receiving packet: %s", strerror(errno));
        }
    }
    
    close(server_socket);
    PACKET_CPU_LOG("🌐 Network receiver thread terminated");
    return NULL;
}

// 🎯 PACKET CPU ENGINE MAIN EXECUTION LOOP
int packet_cpu_engine_run(packet_cpu_engine_t* engine) {
    if (!engine) {
        return -1;
    }
    
    if (engine->running) {
        PACKET_CPU_ERROR("Engine is already running!");
        return -1;
    }
    
    PACKET_CPU_LOG("🚀💥 STARTING PACKET CPU ENGINE 💥🚀");
    PACKET_CPU_LOG("🔥 %u Packet CPU cores ready for execution!", engine->num_cores);
    PACKET_CPU_LOG("🧠 Memory arena: %zu bytes", engine->memory_size);
    PACKET_CPU_LOG("🌐 Listening for packet instructions on port %u", PACKET_CPU_NETWORK_PORT);
    
    // Set global engine reference
    g_engine = engine;
    engine->running = true;
    g_engine_running = true;
    
    // Create network receiver thread
    pthread_t receiver_thread;
    if (pthread_create(&receiver_thread, NULL, packet_cpu_network_receiver, engine) != 0) {
        PACKET_CPU_ERROR("Failed to create network receiver thread");
        engine->running = false;
        g_engine_running = false;
        return -1;
    }
    
    // Main engine monitoring loop
    struct timeval start_time, current_time;
    gettimeofday(&start_time, NULL);
    
    uint32_t last_packets = 0;
    uint64_t last_cycles = 0;
    
    while (engine->running) {
        sleep(1); // Monitor every second
        
        gettimeofday(&current_time, NULL);
        double elapsed = (current_time.tv_sec - start_time.tv_sec) + 
                        (current_time.tv_usec - start_time.tv_usec) / 1000000.0;
        
        uint32_t packets_delta = engine->packets_processed - last_packets;
        uint64_t cycles_delta = engine->total_cycles - last_cycles;
        
        // Print engine stats
        PACKET_CPU_LOG("📊 ENGINE STATS: %.1fs | Packets: %u (+%u/s) | Cycles: %lu (+%lu/s)", 
                      elapsed, engine->packets_processed, packets_delta, 
                      engine->total_cycles, cycles_delta);
        
        // Count active cores
        uint32_t active_cores = 0;
        for (uint32_t i = 0; i < engine->num_cores; i++) {
            if (engine->cores[i] && engine->cores[i]->state.active && 
                !engine->cores[i]->terminated) {
                active_cores++;
            }
        }
        
        PACKET_CPU_LOG("🎯 Active cores: %u/%u", active_cores, engine->num_cores);
        
        last_packets = engine->packets_processed;
        last_cycles = engine->total_cycles;
        
        // Check if all cores are terminated
        if (active_cores == 0) {
            PACKET_CPU_LOG("🛑 All cores terminated - stopping engine");
            break;
        }
    }
    
    // Wait for receiver thread to finish
    engine->running = false;
    g_engine_running = false;
    pthread_join(receiver_thread, NULL);
    
    PACKET_CPU_LOG("🎯 PACKET CPU ENGINE STOPPED");
    PACKET_CPU_LOG("📈 Final Stats: Packets: %u | Cycles: %lu", 
                   engine->packets_processed, engine->total_cycles);
    
    return 0;
}

// 🛑 STOP PACKET CPU ENGINE
void packet_cpu_engine_stop(packet_cpu_engine_t* engine) {
    if (!engine || !engine->running) {
        return;
    }
    
    PACKET_CPU_LOG("🛑 Stopping Packet CPU Engine...");
    engine->running = false;
    g_engine_running = false;
}

// 💀 SIGNAL HANDLER (CLEAN SHUTDOWN - NO OS BULLSHIT!)
void packet_cpu_signal_handler(int signum) {
    PACKET_CPU_LOG("💀 Received signal %d - shutting down packet CPU", signum);
    
    if (g_engine) {
        packet_cpu_engine_stop(g_engine);
    }
    
    g_engine_running = false;
}

// 🎯 BOOTSTRAP FUNCTION (THE ONLY TRADITIONAL PROCESS WE NEED!)
int packet_cpu_bootstrap(uint16_t port) {
    PACKET_CPU_LOG("🔥💥🚀 PACKET CPU BOOTSTRAP INITIATED 🚀💥🔥");
    PACKET_CPU_LOG("🖕 FUCK TRADITIONAL CPUS - WE ARE THE CPU NOW!");
    PACKET_CPU_LOG("📦 PACKETS = INSTRUCTIONS | NETWORKING = PIPELINE | MEMORY = FILESYSTEM");
    
    // Set up signal handlers for clean shutdown
    signal(SIGINT, packet_cpu_signal_handler);
    signal(SIGTERM, packet_cpu_signal_handler);
    
    PACKET_CPU_LOG("✅ Bootstrap complete - Packet CPU ready for revolution!");
    return 0;
}

// 💀 SHUTDOWN FUNCTION (CLEAN PACKET DEATH!)
void packet_cpu_shutdown(void) {
    PACKET_CPU_LOG("💀 PACKET CPU SHUTDOWN INITIATED");
    
    if (g_engine) {
        packet_cpu_engine_destroy(g_engine);
        g_engine = NULL;
    }
    
    PACKET_CPU_LOG("🎯 Packet CPU shutdown complete - returning to caveman computing");
}
