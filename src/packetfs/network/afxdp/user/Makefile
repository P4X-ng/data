# Build libpfs_afxdp.so and CLI tools

CC ?= cc
CFLAGS ?= -O3 -g -DNDEBUG -fPIC -Wall -Wextra
LDFLAGS ?=

BPFCFLAGS := $(shell pkg-config --cflags libbpf 2>/dev/null || pkgconf --cflags libbpf 2>/dev/null)
BPFLIBS   := $(shell pkg-config --libs libbpf 2>/dev/null || pkgconf --libs libbpf 2>/dev/null)
XDPCFLAGS := $(shell pkg-config --cflags libxdp 2>/dev/null || pkgconf --cflags libxdp 2>/dev/null)
XDPLIBS   := $(shell pkg-config --libs libxdp 2>/dev/null || pkgconf --libs libxdp 2>/dev/null)

BUILD := build
LIB   := $(BUILD)/libpfs_afxdp.so
OBJS  := $(BUILD)/pfs_afxdp.o

CLIS  := $(BUILD)/pfs_afxdp_rx $(BUILD)/pfs_afxdp_tx $(BUILD)/pfs_afxdp_status

INCLUDES := -I.

.PHONY: all clean install

all: $(LIB) $(CLIS)
	@echo "[USER] Built $(LIB) and CLIs"

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/pfs_afxdp.o: pfs_afxdp.c pfs_afxdp.h | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(BPFCFLAGS) $(XDPCFLAGS) -c $< -o $@

$(LIB): $(OBJS)
	$(CC) -shared -o $@ $^ $(BPFLIBS) $(XDPLIBS)

$(BUILD)/pfs_afxdp_rx: pfs_afxdp_rx.c pfs_afxdp.h $(LIB)
	$(CC) $(CFLAGS) $(INCLUDES) $(BPFCFLAGS) $(XDPCFLAGS) -o $@ pfs_afxdp_rx.c $(LIB) $(BPFLIBS) $(XDPLIBS) -Wl,-rpath,'$$ORIGIN'

$(BUILD)/pfs_afxdp_tx: pfs_afxdp_tx.c pfs_afxdp.h $(LIB)
	$(CC) $(CFLAGS) $(INCLUDES) $(BPFCFLAGS) $(XDPCFLAGS) -o $@ pfs_afxdp_tx.c $(LIB) $(BPFLIBS) $(XDPLIBS) -Wl,-rpath,'$$ORIGIN'

$(BUILD)/pfs_afxdp_status: pfs_afxdp_status.c pfs_afxdp.h $(LIB)
	$(CC) $(CFLAGS) $(INCLUDES) $(BPFCFLAGS) $(XDPCFLAGS) -o $@ pfs_afxdp_status.c $(LIB) $(BPFLIBS) $(XDPLIBS) -Wl,-rpath,'$$ORIGIN'

clean:
	rm -rf $(BUILD)

install: all
	@echo "(local) install complete — artifacts are in $(BUILD)/"

