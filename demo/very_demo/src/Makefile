# PacketFS Revolutionary Build System
# "Compile at the Speed of Light!" 🚀

CC = gcc
CFLAGS = -Wall -Wextra -O3 -std=c99 -D_GNU_SOURCE -fopenmp
LDFLAGS = -lpthread -lrt -fopenmp
SRCDIR = .
OBJDIR = obj
BINDIR = bin

# Source files
CORE_SRCS = packetfs_core.c
DEMO_SRCS = packetfs_demo.c
ALL_SRCS = $(CORE_SRCS) $(DEMO_SRCS)

# Object files
CORE_OBJS = $(CORE_SRCS:%.c=$(OBJDIR)/%.o)
DEMO_OBJS = $(DEMO_SRCS:%.c=$(OBJDIR)/%.o)
ALL_OBJS = $(ALL_SRCS:%.c=$(OBJDIR)/%.o)

# Targets
TARGET = $(BINDIR)/packetfs_demo
STATIC_TARGET = $(BINDIR)/packetfs_demo_static
MICRO_EXECUTOR = $(BINDIR)/micro_executor
SWARM_COORDINATOR = $(BINDIR)/swarm_coordinator
MEMORY_EXECUTOR = $(BINDIR)/memory_executor

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[0;33m
BLUE = \033[0;34m
MAGENTA = \033[0;35m
CYAN = \033[0;36m
WHITE = \033[0;37m
RESET = \033[0m

.PHONY: all clean demo run interactive benchmark install uninstall help

# Default target
all: banner $(TARGET)
	@echo "$(GREEN)🎉 PacketFS build complete!$(RESET)"
	@echo "$(CYAN)   Run: $(WHITE)./$(TARGET)$(RESET)"
	@echo "$(CYAN)   Interactive: $(WHITE)./$(TARGET) --interactive$(RESET)"

# Create directories
$(OBJDIR) $(BINDIR):
	@mkdir -p $@

# Banner
banner:
	@echo "$(CYAN)🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊$(RESET)"
	@echo "$(CYAN)🌊                                                            🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)        ████████╗ █████╗  ██████╗██╗  ██╗███████╗████████╗ $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)        ██╔══██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝ $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)        ██████╔╝███████║██║     █████╔╝ █████╗     ██║    $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)        ██╔═══╝ ██╔══██║██║     ██╔═██╗ ██╔══╝     ██║    $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)        ██║     ██║  ██║╚██████╗██║  ██╗███████╗   ██║    $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)        ╚═╝     ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝    $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊                                                            🌊$(RESET)"
	@echo "$(CYAN)🌊$(WHITE)          \"Storage IS Packets, Execution IS Network Flow\"  $(CYAN)🌊$(RESET)"
	@echo "$(CYAN)🌊                                                            🌊$(RESET)"
	@echo "$(CYAN)🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊🌊$(RESET)"

# Compile object files
$(OBJDIR)/%.o: %.c | $(OBJDIR)
	@echo "$(YELLOW)📦 Compiling $<...$(RESET)"
	$(CC) $(CFLAGS) -c $< -o $@

# Link main target
$(TARGET): $(ALL_OBJS) | $(BINDIR)
	@echo "$(GREEN)🔗 Linking PacketFS demo...$(RESET)"
	$(CC) $(ALL_OBJS) -o $@ $(LDFLAGS)
	@chmod +x $@

# Static build for portability
static: $(STATIC_TARGET)

$(STATIC_TARGET): $(ALL_OBJS) | $(BINDIR)
	@echo "$(GREEN)🔗 Linking static PacketFS demo...$(RESET)"
	$(CC) $(ALL_OBJS) -o $@ $(LDFLAGS) -static
	@chmod +x $@

# Run demo automatically
demo: $(TARGET)
	@echo "$(MAGENTA)🚀 Running PacketFS demo...$(RESET)"
	./$(TARGET)

# Run demo in interactive mode
interactive: $(TARGET)
	@echo "$(MAGENTA)🎯 Running PacketFS interactive demo...$(RESET)"
	./$(TARGET) --interactive

# Quick run alias
run: demo

# Performance benchmark
benchmark: $(TARGET)
	@echo "$(RED)⚡ Running PacketFS benchmarks...$(RESET)"
	@echo "$(YELLOW)Creating 10GB test filesystem...$(RESET)"
	time ./$(TARGET) --benchmark

# Install to system
install: $(TARGET)
	@echo "$(GREEN)📥 Installing PacketFS...$(RESET)"
	sudo cp $(TARGET) /usr/local/bin/packetfs
	sudo chmod +x /usr/local/bin/packetfs
	@echo "$(GREEN)✅ PacketFS installed to /usr/local/bin/packetfs$(RESET)"

# Uninstall from system
uninstall:
	@echo "$(RED)🗑️ Uninstalling PacketFS...$(RESET)"
	sudo rm -f /usr/local/bin/packetfs
	@echo "$(GREEN)✅ PacketFS uninstalled$(RESET)"

# Clean build files
clean:
	@echo "$(RED)🧹 Cleaning build files...$(RESET)"
	rm -rf $(OBJDIR) $(BINDIR) *.packetfs
	@echo "$(GREEN)✅ Clean complete$(RESET)"

# Debug build with symbols
debug: CFLAGS += -g -DDEBUG -O0
debug: clean $(TARGET)
	@echo "$(YELLOW)🐛 Debug build complete$(RESET)"

# Release build with maximum optimization
release: CFLAGS += -O3 -DNDEBUG -march=native -mtune=native
release: clean $(TARGET)
	@echo "$(GREEN)🚀 Release build complete - MAXIMUM SPEED!$(RESET)"

# Profile-guided optimization build
pgo: CFLAGS += -fprofile-generate
pgo: clean $(TARGET)
	@echo "$(CYAN)📊 Running PGO training...$(RESET)"
	./$(TARGET) > /dev/null 2>&1 || true
	$(MAKE) clean
	$(MAKE) CFLAGS="$(CFLAGS) -fprofile-use" $(TARGET)
	@echo "$(GREEN)⚡ PGO build complete - LUDICROUS SPEED!$(RESET)"

# Memory leak check
memcheck: debug
	@echo "$(MAGENTA)🔍 Running memory leak check...$(RESET)"
	valgrind --leak-check=full --show-leak-kinds=all ./$(TARGET)

# Code analysis
analyze:
	@echo "$(BLUE)🔬 Running static analysis...$(RESET)"
	clang-tidy $(ALL_SRCS) -- $(CFLAGS)

# Enhanced demo compilation
enhanced_demo:
	@echo "$(GREEN)🚀 Compiling enhanced demo...$(RESET)"
	gcc -O3 -march=native -fopenmp -Wall -Wextra -o demo_enhanced demo_enhanced.c -lm -lpthread
	@echo "$(GREEN)✅ Enhanced demo ready!$(RESET)"

# Run enhanced demo
run_enhanced:
	@echo "$(MAGENTA)💫 Running enhanced PacketFS demo...$(RESET)"
	./demo_enhanced 2 200

# Test enhanced demo with larger sizes
test_enhanced:
	@echo "$(RED)⚡ Running enhanced demo stress test...$(RESET)"
	./demo_enhanced 5 500

# Performance profiling
profile: debug
	@echo "$(CYAN)📈 Running performance profiler...$(RESET)"
	perf record -g ./$(TARGET)
	perf report

# Help menu
help:
	@echo "$(WHITE)🌊 PacketFS Build System Help$(RESET)"
	@echo "$(YELLOW)════════════════════════════════════════$(RESET)"
	@echo "$(GREEN)Basic Targets:$(RESET)"
	@echo "  $(CYAN)all$(RESET)         - Build PacketFS demo"
	@echo "  $(CYAN)demo$(RESET)        - Build and run demo automatically"
	@echo "  $(CYAN)interactive$(RESET) - Build and run interactive demo"
	@echo "  $(CYAN)run$(RESET)         - Alias for demo"
	@echo "  $(CYAN)clean$(RESET)       - Clean all build files"
	@echo ""
	@echo "$(GREEN)Build Variants:$(RESET)"
	@echo "  $(CYAN)debug$(RESET)       - Debug build with symbols"
	@echo "  $(CYAN)release$(RESET)     - Optimized release build"
	@echo "  $(CYAN)static$(RESET)      - Static binary for portability"
	@echo "  $(CYAN)pgo$(RESET)         - Profile-guided optimization"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  $(CYAN)memcheck$(RESET)    - Check for memory leaks"
	@echo "  $(CYAN)analyze$(RESET)     - Static code analysis"
	@echo "  $(CYAN)profile$(RESET)     - Performance profiling"
	@echo "  $(CYAN)benchmark$(RESET)   - Performance benchmarks"
	@echo ""
	@echo "$(GREEN)System:$(RESET)"
	@echo "  $(CYAN)install$(RESET)     - Install to /usr/local/bin"
	@echo "  $(CYAN)uninstall$(RESET)   - Remove from system"
	@echo ""
	@echo "$(MAGENTA)Ready to revolutionize computing? 🚀$(RESET)"

# Show compiler and system info
info:
	@echo "$(WHITE)🖥️ Build Environment Information$(RESET)"
	@echo "$(YELLOW)════════════════════════════════════════$(RESET)"
	@echo "$(GREEN)Compiler:$(RESET) $(shell $(CC) --version | head -n1)"
	@echo "$(GREEN)System:$(RESET) $(shell uname -a)"
	@echo "$(GREEN)CPU:$(RESET) $(shell lscpu | grep 'Model name' | cut -d: -f2 | sed 's/^ *//')"
	@echo "$(GREEN)Memory:$(RESET) $(shell free -h | grep Mem | awk '{print $$2}')"
	@echo "$(GREEN)Storage:$(RESET) $(shell df -h . | tail -n1 | awk '{print $$4}') free"
	@echo ""
	@echo "$(CYAN)🎯 Optimal for PacketFS performance!$(RESET)"

# ==============================================================================
# PACKETFS MICRO-EXECUTOR PROCESS SWARM SYSTEM 🚀💎
# Ultra-minimal processes for single instruction execution
# ==============================================================================

# Micro-executor compilation flags (ultra-optimized)
MICRO_CFLAGS = -Wall -Wextra -O3 -march=native -flto -fomit-frame-pointer -s
MICRO_LDFLAGS = -lrt -lpthread -static

# Build micro-executor (ultra-minimal single instruction executor)
$(MICRO_EXECUTOR): micro_executor.c | $(BINDIR)
	@echo "$(GREEN)🔥 Building ultra-minimal micro-executor...$(RESET)"
	$(CC) $(MICRO_CFLAGS) -Os -o $@ $< $(MICRO_LDFLAGS)
	strip --strip-all $@
	@echo "$(GREEN)   ✅ Size: $(WHITE)$$(du -h $@ | cut -f1)$(RESET)"

# Build swarm coordinator
$(SWARM_COORDINATOR): swarm_coordinator.c | $(BINDIR)
	@echo "$(GREEN)🌊 Building process swarm coordinator...$(RESET)"
	$(CC) $(CFLAGS) -g -o $@ $< $(LDFLAGS)
	@echo "$(GREEN)   ✅ Size: $(WHITE)$$(du -h $@ | cut -f1)$(RESET)"

# Build both micro-executor components
micro: $(MICRO_EXECUTOR) $(SWARM_COORDINATOR)
	@echo "$(GREEN)💎 PacketFS Micro-Executor System ready!$(RESET)"
	@echo "$(CYAN)   Test: $(WHITE)make micro_test$(RESET)"
	@echo "$(CYAN)   Benchmark: $(WHITE)make micro_benchmark$(RESET)"

# Quick test with 100 processes
micro_test: micro
	@echo "$(MAGENTA)🧪 Running PacketFS Process Swarm test (100 processes)...$(RESET)"
	./$(SWARM_COORDINATOR) 100

# Benchmark with increasing process counts
micro_benchmark: micro
	@echo "$(RED)📊 Running PacketFS Process Swarm benchmarks...$(RESET)"
	@echo "$(YELLOW)=== Testing 100 processes ===$(RESET)"
	./$(SWARM_COORDINATOR) 100
	@echo "$(YELLOW)\n=== Testing 500 processes ===$(RESET)"
	./$(SWARM_COORDINATOR) 500
	@echo "$(YELLOW)\n=== Testing 1000 processes ===$(RESET)"
	./$(SWARM_COORDINATOR) 1000
	@echo "$(YELLOW)\n=== Testing 2500 processes ===$(RESET)"
	./$(SWARM_COORDINATOR) 2500

# Stress test with system limits
micro_stress: micro
	@echo "$(RED)🔥 PACKETFS PROCESS SWARM STRESS TEST$(RESET)"
	@echo "$(YELLOW)System limits:$(RESET)"
	@echo "  Max processes: $$(ulimit -u)"
	@echo "  Max open files: $$(ulimit -n)"
	@echo "  Available memory: $$(free -h | grep '^Mem:' | awk '{print $$7}')"
	@max_procs=$$(echo "$$(ulimit -u) * 0.1" | bc | cut -d. -f1); \
	echo "$(GREEN)Attempting $$max_procs processes...$(RESET)"; \
	./$(SWARM_COORDINATOR) $$max_procs

# Analyze micro-executor binaries
micro_analyze: micro
	@echo "$(BLUE)🔍 PACKETFS MICRO-EXECUTOR ANALYSIS$(RESET)"
	@echo "$(YELLOW)==========================$(RESET)"
	@echo "$(GREEN)micro_executor:$(RESET)"
	@echo "  Size: $$(du -h $(MICRO_EXECUTOR) | cut -f1)"
	@echo "  Type: $$(file $(MICRO_EXECUTOR))"
	@echo "  Symbols: $$(nm $(MICRO_EXECUTOR) 2>/dev/null | wc -l) symbols"
	@echo ""
	@echo "$(GREEN)swarm_coordinator:$(RESET)"
	@echo "  Size: $$(du -h $(SWARM_COORDINATOR) | cut -f1)"
	@echo "  Type: $$(file $(SWARM_COORDINATOR))"
	@echo "  Symbols: $$(nm $(SWARM_COORDINATOR) 2>/dev/null | wc -l) symbols"

# Show system capabilities for PacketFS
micro_sysinfo:
	@echo "$(BLUE)🖥️  PACKETFS SYSTEM ANALYSIS$(RESET)"
	@echo "$(YELLOW)=============================$(RESET)"
	@echo "$(GREEN)CPU info:$(RESET)"
	@echo "  Cores: $$(nproc) physical, $$(nproc --all) logical"
	@echo "  Architecture: $$(uname -m)"
	@echo ""
	@echo "$(GREEN)Memory info:$(RESET)"
	@echo "  Total RAM: $$(free -h | grep '^Mem:' | awk '{print $$2}')"
	@echo "  Available: $$(free -h | grep '^Mem:' | awk '{print $$7}')"
	@echo "  Page size: $$(getconf PAGESIZE) bytes"
	@echo ""
	@echo "$(GREEN)Process limits:$(RESET)"
	@echo "  Max user processes: $$(ulimit -u)"
	@echo "  Max open files: $$(ulimit -n)"
	@echo ""
	@max_procs=$$(echo "$$(ulimit -u) * 0.1" | bc | cut -d. -f1); \
	echo "$(GREEN)Estimated PacketFS capacity:$(RESET)"; \
	echo "  Safe process limit: $$max_procs"; \
	ops_per_sec=$$(echo "$$max_procs * 1000000" | bc); \
	echo "  Theoretical ops/sec: $$ops_per_sec"; \
	equivalent_ghz=$$(echo "scale=2; $$ops_per_sec / 1000000000" | bc); \
	echo "  Equivalent CPU freq: $${equivalent_ghz} GHz"

# Clean micro-executor builds
micro_clean:
	@echo "$(RED)🧹 Cleaning micro-executor builds...$(RESET)"
	rm -f $(MICRO_EXECUTOR) $(SWARM_COORDINATOR)
	@echo "$(GREEN)✅ Micro-executor clean complete$(RESET)"

# ==============================================================================
# PACKETFS MEMORY-BASED EXECUTOR 🧠💥⚡
# NO FILE DESCRIPTORS! MEMORY IS THE FILESYSTEM!
# ==============================================================================

# Build memory-based executor
$(MEMORY_EXECUTOR): memory_executor.c | $(BINDIR)
	@echo "$(GREEN)🧠 Building memory-based executor (NO FILE DESCRIPTORS!)...$(RESET)"
	$(CC) $(CFLAGS) -O3 -march=native -o $@ $< $(LDFLAGS)
	@echo "$(GREEN)   ✅ Size: $(WHITE)$$(du -h $@ | cut -f1)$(RESET)"

# Build memory executor
memory: $(MEMORY_EXECUTOR)
	@echo "$(GREEN)💥 PacketFS Memory Executor ready!$(RESET)"
	@echo "$(CYAN)   Test: $(WHITE)make memory_test$(RESET)"
	@echo "$(CYAN)   Benchmark: $(WHITE)make memory_benchmark$(RESET)"

# Test memory executor with different scales
memory_test: memory
	@echo "$(MAGENTA)🧪 Running PacketFS Memory Executor test (1000 workers)...$(RESET)"
	./$(MEMORY_EXECUTOR) 1000

# Memory executor benchmarks - NO FILE DESCRIPTOR LIMITS!
memory_benchmark: memory
	@echo "$(RED)📊 Running PacketFS Memory Executor benchmarks...$(RESET)"
	@echo "$(YELLOW)=== Testing 1000 memory workers ===$(RESET)"
	./$(MEMORY_EXECUTOR) 1000
	@echo "$(YELLOW)\n=== Testing 5000 memory workers ===$(RESET)"
	./$(MEMORY_EXECUTOR) 5000
	@echo "$(YELLOW)\n=== Testing 10000 memory workers ===$(RESET)"
	./$(MEMORY_EXECUTOR) 10000
	@echo "$(YELLOW)\n=== Testing 25000 memory workers ===$(RESET)"
	./$(MEMORY_EXECUTOR) 25000

# Memory executor stress test - push to system limits
memory_stress: memory
	@echo "$(RED)🔥 PACKETFS MEMORY EXECUTOR STRESS TEST$(RESET)"
	@echo "$(YELLOW)NO FILE DESCRIPTORS = NO LIMITS!$(RESET)"
	@echo "$(YELLOW)System capabilities:$(RESET)"
	@echo "  Available processes: $$(ulimit -u)"
	@echo "  Available memory: $$(free -h | grep '^Mem:' | awk '{print $$7}')"
	@max_procs=$$(echo "$$(ulimit -u) * 0.5" | bc | cut -d. -f1); \
	echo "$(GREEN)Attempting $$max_procs memory workers...$(RESET)"; \
	./$(MEMORY_EXECUTOR) $$max_procs

# Compare memory vs file descriptor approaches
memory_vs_fd: memory micro
	@echo "$(BLUE)⚔️ MEMORY VS FILE DESCRIPTORS SHOWDOWN!$(RESET)"
	@echo "$(YELLOW)Testing same workload on both systems...$(RESET)"
	@echo "\n$(CYAN)=== File Descriptor Approach (limited to ~1000) ===$(RESET)"
	time ./$(SWARM_COORDINATOR) 1000
	@echo "\n$(CYAN)=== Memory Approach (unlimited!) ===$(RESET)"
	time ./$(MEMORY_EXECUTOR) 1000
	@echo "\n$(CYAN)=== Memory Approach (10x scale!) ===$(RESET)"
	time ./$(MEMORY_EXECUTOR) 10000

# Clean memory executor builds
memory_clean:
	@echo "$(RED)🧹 Cleaning memory executor builds...$(RESET)"
	rm -f $(MEMORY_EXECUTOR)
	@echo "$(GREEN)✅ Memory executor clean complete$(RESET)"

# ==============================================================================
# 🔥💀 PACKET CPU REVOLUTION 💀🔥
# FUCK TRADITIONAL CPUS - WE ARE THE CPU!
# PACKETS = INSTRUCTIONS | NETWORKING = PIPELINE | MEMORY = FILESYSTEM
# ==============================================================================

# Packet CPU targets
PACKET_CPU_TEST = $(BINDIR)/packet_cpu_test
PACKET_CPU_SOURCES = packet_cpu_core.c packet_cpu_engine.c packet_cpu_test.c
PACKET_CPU_OBJECTS = $(PACKET_CPU_SOURCES:%.c=$(OBJDIR)/%.o)

# Build the packet CPU revolution!
packet_cpu: $(PACKET_CPU_TEST)
	@echo "$(RED)🔥💥🚀 PACKET CPU REVOLUTION BUILD COMPLETE! 🚀💥🔥$(RESET)"
	@echo "$(YELLOW)🖕 FUCK TRADITIONAL CPUS - PACKETS ARE THE NEW INSTRUCTIONS!$(RESET)"
	@echo "$(GREEN)🌐 NETWORKING IS THE NEW EXECUTION PIPELINE!$(RESET)"
	@echo "$(CYAN)💎 RUN: $(WHITE)./$(PACKET_CPU_TEST) [cores] [instructions]$(RESET)"

# Build packet CPU test executable
$(PACKET_CPU_TEST): $(PACKET_CPU_OBJECTS) | $(BINDIR)
	@echo "$(GREEN)🔗 Linking Packet CPU Revolution...$(RESET)"
	$(CC) $(PACKET_CPU_OBJECTS) -o $@ $(LDFLAGS) -pthread -lrt
	@echo "$(GREEN)   ✅ Packet CPU revolutionary executable ready: $@$(RESET)"

# Compile packet CPU object files
$(OBJDIR)/packet_cpu_%.o: packet_cpu_%.c packet_cpu.h | $(OBJDIR)
	@echo "$(YELLOW)🔥 Compiling $<...$(RESET)"
	$(CC) $(CFLAGS) -c $< -o $@

# Packet CPU test suite
test-packet-cpu-small: packet_cpu
	@echo "$(MAGENTA)🧪 Small Packet CPU test (100 cores, 1K instructions)$(RESET)"
	./$(PACKET_CPU_TEST) 100 1000

test-packet-cpu: packet_cpu
	@echo "$(MAGENTA)🚀💥 LAUNCHING PACKET CPU REVOLUTION TEST! 💥🚀$(RESET)"
	./$(PACKET_CPU_TEST) 1000 10000

test-packet-cpu-medium: packet_cpu
	@echo "$(RED)🔥 Medium Packet CPU test (5K cores, 50K instructions)$(RESET)"
	./$(PACKET_CPU_TEST) 5000 50000

test-packet-cpu-large: packet_cpu
	@echo "$(RED)💥 Large Packet CPU test (25K cores, 250K instructions)$(RESET)"
	./$(PACKET_CPU_TEST) 25000 250000

test-packet-cpu-massive: packet_cpu
	@echo "$(RED)🌋 MASSIVE Packet CPU test (100K cores, 1M instructions)$(RESET)"
	./$(PACKET_CPU_TEST) 100000 1000000

test-packet-cpu-revolution: packet_cpu
	@echo "$(RED)🔥💀💥 THE ULTIMATE PACKET CPU REVOLUTION! 💥💀🔥$(RESET)"
	@echo "$(YELLOW)🚀 1.3 MILLION PACKET CPU CORES!$(RESET)"
	@echo "$(YELLOW)📦 5 MILLION PACKET INSTRUCTIONS!$(RESET)"
	@echo "$(YELLOW)🌐 PURE NETWORK-BASED EXECUTION!$(RESET)"
	./$(PACKET_CPU_TEST) 1300000 5000000

# Clean packet CPU builds
packet_cpu_clean:
	@echo "$(RED)🧹 Cleaning packet CPU builds...$(RESET)"
	rm -f $(PACKET_CPU_TEST) $(OBJDIR)/packet_cpu_*.o
	@echo "$(GREEN)✅ Packet CPU clean complete$(RESET)"
