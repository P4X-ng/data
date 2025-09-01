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
