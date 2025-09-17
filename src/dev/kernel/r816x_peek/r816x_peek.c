// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/pci_regs.h>
#include <linux/io.h>
#include <linux/uaccess.h>

static char *bdf = "0000:82:00.0";
module_param(bdf, charp, 0400);
MODULE_PARM_DESC(bdf, "PCI BDF of Realtek 8168/8169 (e.g., 0000:82:00.0)");

// Realtek RTL8168/9 register offsets of interest
#define R816X_TNPDS_LO 0x20  // TX Normal Priority Desc Start Low
#define R816X_TNPDS_HI 0x24  // High
#define R816X_RDSAR_LO 0xE4  // RX Desc Start Low
#define R816X_RDSAR_HI 0xE8  // High

static void __iomem *mmio;
static void __iomem *mmio0;
static resource_size_t mmio_start, mmio_len;
static resource_size_t mmio0_start, mmio0_len;
static struct pci_dev *pdev;

static void dump_dw(void __iomem *base, u32 start, u32 bytes)
{
    u32 off;
    for (off = start; off < start + bytes; off += 16) {
        u32 v0 = readl(base + off + 0);
        u32 v1 = readl(base + off + 4);
        u32 v2 = readl(base + off + 8);
        u32 v3 = readl(base + off + 12);
        pr_info("r816x_peek: mmio[0x%03x]: %08x %08x %08x %08x\n", off, v0, v1, v2, v3);
    }
}

static void read_bases(void __iomem *base, const char *tag)
{
    u32 t_lo = readl(base + R816X_TNPDS_LO);
    u32 t_hi = readl(base + R816X_TNPDS_HI);
    u32 r_lo = readl(base + R816X_RDSAR_LO);
    u32 r_hi = readl(base + R816X_RDSAR_HI);
    u64 t_base = ((u64)t_hi << 32) | t_lo;
    u64 r_base = ((u64)r_hi << 32) | r_lo;
    pr_info("r816x_peek: %s TNPDS=0x%016llx RDSAR=0x%016llx\n",
            tag, (unsigned long long)t_base, (unsigned long long)r_base);
}

static int r816x_peek_probe(void)
{
    unsigned int dom, bus, dev, fn;
    if (sscanf(bdf, "%x:%x:%x.%x", &dom, &bus, &dev, &fn) != 4) {
        pr_err("r816x_peek: invalid bdf=%s\n", bdf);
        return -EINVAL;
    }
    pdev = pci_get_domain_bus_and_slot(dom, bus, PCI_DEVFN(dev, fn));
    if (!pdev) {
        pr_err("r816x_peek: pci dev %s not found\n", bdf);
        return -ENODEV;
    }

    // Do not claim device; just ioremap the BARs used for MMIO
    // Map BAR2 (common on many 8168 revs) and BAR0 as fallback/extra
    mmio_start = pci_resource_start(pdev, 2);
    mmio_len   = pci_resource_len(pdev, 2);
    mmio0_start = pci_resource_start(pdev, 0);
    mmio0_len   = pci_resource_len(pdev, 0);

    if (mmio_start && mmio_len)
        mmio = ioremap(mmio_start, mmio_len);
    if (mmio0_start && mmio0_len)
        mmio0 = ioremap(mmio0_start, mmio0_len);

    if (!mmio && !mmio0) {
        pr_err("r816x_peek: failed to ioremap BAR2 and BAR0 for %s\n", bdf);
        return -ENOMEM;
    }

    // PCI config command (bus mastering etc.)
    {
        u16 pcicmd = 0; u32 bar0l=0, bar2l=0;
        pci_read_config_word(pdev, PCI_COMMAND, &pcicmd);
        pci_read_config_dword(pdev, PCI_BASE_ADDRESS_0, &bar0l);
        pci_read_config_dword(pdev, PCI_BASE_ADDRESS_2, &bar2l);
        pr_info("r816x_peek: PCI cmd=0x%04x BAR0=0x%08x BAR2=0x%08x\n", pcicmd, bar0l, bar2l);
    }

    if (mmio) {
        pr_info("r816x_peek: %s BAR2 mmio=%pa len=%pa\n", bdf, &mmio_start, &mmio_len);
        read_bases(mmio, "BAR2");
        // Dump small windows: 0x00..0x40 and 0xE0..0x100
        dump_dw(mmio, 0x00, 0x40);
        dump_dw(mmio, 0xE0, 0x20);
    }
    if (mmio0) {
        pr_info("r816x_peek: %s BAR0 mmio=%pa len=%pa\n", bdf, &mmio0_start, &mmio0_len);
        read_bases(mmio0, "BAR0");
        dump_dw(mmio0, 0x00, 0x40);
        dump_dw(mmio0, 0xE0, 0x20);
    }

    return 0;
}

static void r816x_peek_remove(void)
{
    if (mmio) { iounmap(mmio); mmio = NULL; }
    if (mmio0) { iounmap(mmio0); mmio0 = NULL; }
    if (pdev) { pci_dev_put(pdev); pdev = NULL; }
}

static int __init r816x_peek_init(void)
{
    pr_info("r816x_peek: init (read-only peek)\n");
    return r816x_peek_probe();
}

static void __exit r816x_peek_exit(void)
{
    pr_info("r816x_peek: exit\n");
    r816x_peek_remove();
}

MODULE_AUTHOR("PacketFS");
MODULE_DESCRIPTION("Read-only peek of Realtek 816x ring base registers");
MODULE_LICENSE("GPL");
module_init(r816x_peek_init);
module_exit(r816x_peek_exit);

