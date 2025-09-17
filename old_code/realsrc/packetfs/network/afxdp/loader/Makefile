# Build the standalone XDP loader

CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra
LDFLAGS ?=
BPFDIRS := $(shell pkg-config --cflags libbpf 2>/dev/null || pkgconf --cflags libbpf 2>/dev/null)
BPFLIBS := $(shell pkg-config --libs libbpf 2>/dev/null || pkgconf --libs libbpf 2>/dev/null)

BUILD := build
BIN := $(BUILD)/pfs_xdp_loader
SRC := pfs_xdp_loader.c

.PHONY: all clean

all: $(BIN)
	@echo "[LOADER] Built $(BIN)"

$(BIN): $(SRC)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(BPFDIRS) -o $(BIN) $(SRC) $(BPFLIBS)

clean:
	rm -rf $(BUILD)

