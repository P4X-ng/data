# BPF build for AF_XDP redirector
# Outputs go into build/

BPF_CLANG ?= clang
BPFOBJ_DIR := build
BPFOBJ := $(BPFOBJ_DIR)/pfs_kern.bpf.o
SKEL := $(BPFOBJ_DIR)/pfs_kern.skel.h
SRC := pfs_kern.bpf.c

# Default: x86-64. Override by invoking `make ARCH=arm64`.
ARCH ?= x86
TARGET_MACRO := __TARGET_ARCH_$(ARCH)

.PHONY: all clean

all: $(BPFOBJ) $(SKEL)
	@echo "[BPF] Built $(BPFOBJ) and $(SKEL)"

$(BPFOBJ): $(SRC)
	@mkdir -p $(BPFOBJ_DIR)
	$(BPF_CLANG) -O2 -g -target bpf -D$(TARGET_MACRO) -c $(SRC) -o $(BPFOBJ)

$(SKEL): $(BPFOBJ)
	bpftool gen skeleton $(BPFOBJ) > $(SKEL)

clean:
	rm -rf $(BPFOBJ_DIR)

