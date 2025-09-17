// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/mm.h>
#include <linux/io.h>
#include <linux/slab.h>
#include <linux/debugfs.h>

#include "../../../realsrc/packetfs/uapi/pfs_ringpeek.h"

#define DRV_NAME "pfs_ringpeek"
#define PFS_RINGPEEK_MAX_WINDOW (64*1024) /* cap mapped window size */

struct pfs_ringpeek_dev {
    struct pci_dev *pdev;
    void __iomem *bar_addr;
    resource_size_t bar_len;
    u32 bar_index;
    u64 offset;
    u32 length;
    struct dentry *dbg_dir;
    struct dentry *dbg_file;
};

static struct pfs_ringpeek_dev *gdev;

static long pfs_ringpeek_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    if (!gdev) return -ENODEV;

    switch (cmd) {
    case PFS_RINGPEEK_IOC_SET_WINDOW: {
        struct pfs_ringpeek_window win;
        if (copy_from_user(&win, (void __user *)arg, sizeof(win)))
            return -EFAULT;
        if (win.bar > 5) return -EINVAL;
        if (win.length == 0 || win.length > PFS_RINGPEEK_MAX_WINDOW)
            return -EINVAL;

        /* Map requested BAR if different */
        if (!gdev->pdev) return -ENODEV;
        if (gdev->bar_addr && gdev->bar_index != win.bar) {
            iounmap(gdev->bar_addr);
            gdev->bar_addr = NULL;
        }
        if (!gdev->bar_addr || gdev->bar_index != win.bar) {
            resource_size_t start = pci_resource_start(gdev->pdev, win.bar);
            resource_size_t len = pci_resource_len(gdev->pdev, win.bar);
            if (!start || !len) return -EINVAL;
            if (!(pci_resource_flags(gdev->pdev, win.bar) & IORESOURCE_MEM))
                return -EINVAL;
            gdev->bar_addr = ioremap(start, len);
            if (!gdev->bar_addr) return -ENOMEM;
            gdev->bar_len = len;
            gdev->bar_index = win.bar;
        }
        if (win.offset + win.length > gdev->bar_len)
            return -EINVAL;
        gdev->offset = win.offset;
        gdev->length = win.length;
        return 0;
    }
    case PFS_RINGPEEK_IOC_GET_INFO: {
        struct pfs_ringpeek_info info = {0};
        if (!gdev->pdev) return -ENODEV;
        info.vendor = gdev->pdev->vendor;
        info.device = gdev->pdev->device;
        info.domain = pci_domain_nr(gdev->pdev->bus);
        info.bus = gdev->pdev->bus->number;
        info.slot = PCI_SLOT(gdev->pdev->devfn);
        info.func = PCI_FUNC(gdev->pdev->devfn);
        info.bar_size = gdev->bar_len;
        if (copy_to_user((void __user *)arg, &info, sizeof(info)))
            return -EFAULT;
        return 0;
    }
    default:
        return -ENOTTY;
    }
}

static ssize_t pfs_ringpeek_read(struct file *filp, char __user *buf, size_t len, loff_t *ppos)
{
    size_t to_copy;
    if (!gdev || !gdev->bar_addr) return -ENODEV;
    if (*ppos >= gdev->length) return 0;
    to_copy = min(len, (size_t)(gdev->length - *ppos));

    /* Use memcpy_fromio into a temporary buffer to avoid exposing kernel pointers */
    if (to_copy) {
        void *tmp = kmalloc(to_copy, GFP_KERNEL);
        if (!tmp) return -ENOMEM;
        memcpy_fromio(tmp, gdev->bar_addr + gdev->offset + *ppos, to_copy);
        if (copy_to_user(buf, tmp, to_copy)) { kfree(tmp); return -EFAULT; }
        kfree(tmp);
        *ppos += to_copy;
    }
    return to_copy;
}

static int pfs_ringpeek_mmap(struct file *filp, struct vm_area_struct *vma)
{
    /* For safety, disable mmap of MMIO; force read() path */
    return -ENOSYS;
}

static const struct file_operations pfs_ringpeek_fops = {
    .owner          = THIS_MODULE,
    .unlocked_ioctl = pfs_ringpeek_ioctl,
#ifdef CONFIG_COMPAT
    .compat_ioctl   = pfs_ringpeek_ioctl,
#endif
    .read           = pfs_ringpeek_read,
    .mmap           = pfs_ringpeek_mmap,
    .llseek         = default_llseek,
};

static struct miscdevice pfs_ringpeek_miscdev = {
    .minor = MISC_DYNAMIC_MINOR,
    .name  = DRV_NAME,
    .fops  = &pfs_ringpeek_fops,
    .mode  = 0600,
};

static ssize_t dbg_dump_read(struct file *f, char __user *buf, size_t len, loff_t *ppos)
{
    /* Dump current window via debugfs */
    return pfs_ringpeek_read(NULL, buf, len, ppos);
}

static const struct file_operations dbgfs_fops = {
    .owner = THIS_MODULE,
    .read  = dbg_dump_read,
    .llseek = default_llseek,
};

static int __init pfs_ringpeek_init(void)
{
    int ret;
    /* Find the Realtek PCI device currently bound to r8169 (non-intrusive) */
    struct pci_dev *pdev = NULL;
    for_each_pci_dev(pdev) {
        if (pdev->vendor == PCI_VENDOR_ID_REALTEK &&
            (pdev->device == 0x8168 || pdev->device == 0x8169)) {
            gdev = kzalloc(sizeof(*gdev), GFP_KERNEL);
            if (!gdev) return -ENOMEM;
            gdev->pdev = pdev;
            break;
        }
    }
    if (!gdev) return -ENODEV;

    ret = misc_register(&pfs_ringpeek_miscdev);
    if (ret) { kfree(gdev); gdev = NULL; return ret; }

    gdev->dbg_dir = debugfs_create_dir(DRV_NAME, NULL);
    if (IS_ERR_OR_NULL(gdev->dbg_dir)) gdev->dbg_dir = NULL;
    if (gdev->dbg_dir)
        gdev->dbg_file = debugfs_create_file("dump", 0400, gdev->dbg_dir, NULL, &dbgfs_fops);

    pr_info(DRV_NAME ": ready; use ioctl to set BAR window, then read() or debugfs dump\n");
    return 0;
}

static void __exit pfs_ringpeek_exit(void)
{
    if (gdev) {
        if (gdev->dbg_file) debugfs_remove(gdev->dbg_file);
        if (gdev->dbg_dir) debugfs_remove(gdev->dbg_dir);
        if (gdev->bar_addr) iounmap(gdev->bar_addr);
        kfree(gdev);
        gdev = NULL;
    }
    misc_deregister(&pfs_ringpeek_miscdev);
    pr_info(DRV_NAME ": exit\n");
}

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("PacketFS ring peek (read-only MMIO window)");
MODULE_AUTHOR("PacketFS");

module_init(pfs_ringpeek_init);
module_exit(pfs_ringpeek_exit);