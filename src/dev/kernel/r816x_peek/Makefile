# SPDX-License-Identifier: GPL-2.0
# Simple out-of-tree module build
obj-m += r816x_peek.o

KDIR := /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

