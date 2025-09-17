# SPDX-License-Identifier: MIT
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra

all: pfs_ringpeek_ctl pfs_afpkt_rx

pfs_ringpeek_ctl: pfs_ringpeek_ctl.c ../../../realsrc/packetfs/uapi/pfs_ringpeek.h
	$(CC) $(CFLAGS) -o $@ $<

pfs_afpkt_rx: pfs_afpkt_rx.c ../../../realsrc/packetfs/memory/pfs_hugeblob.c ../../../realsrc/packetfs/memory/pfs_hugeblob.h ../../../realsrc/packetfs/pcpu/pfs_pcpu.c
	$(CC) $(CFLAGS) -I../../../realsrc/packetfs -o $@ pfs_afpkt_rx.c \
	  ../../../realsrc/packetfs/memory/pfs_hugeblob.c \
	  ../../../realsrc/packetfs/pcpu/pfs_pcpu.c

clean:
	rm -f pfs_ringpeek_ctl pfs_afpkt_rx
