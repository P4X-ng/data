#include <linux/module.h>
#include <linux/export-internal.h>
#include <linux/compiler.h>

MODULE_INFO(name, KBUILD_MODNAME);

__visible struct module __this_module
__section(".gnu.linkonce.this_module") = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};



static const struct modversion_info ____versions[]
__used __section("__versions") = {
	{ 0x12ad300e, "iounmap" },
	{ 0xe902a12b, "pci_dev_put" },
	{ 0x173ec8da, "sscanf" },
	{ 0x0166f74b, "pci_get_domain_bus_and_slot" },
	{ 0x97dd6ca9, "ioremap" },
	{ 0x8aff9a19, "pci_read_config_word" },
	{ 0x011d8503, "pci_read_config_dword" },
	{ 0xd272d446, "__stack_chk_fail" },
	{ 0x73bebd3f, "param_ops_charp" },
	{ 0xd272d446, "__fentry__" },
	{ 0xe8213e80, "_printk" },
	{ 0xd272d446, "__x86_return_thunk" },
	{ 0x70eca2ca, "module_layout" },
};

static const u32 ____version_ext_crcs[]
__used __section("__version_ext_crcs") = {
	0x12ad300e,
	0xe902a12b,
	0x173ec8da,
	0x0166f74b,
	0x97dd6ca9,
	0x8aff9a19,
	0x011d8503,
	0xd272d446,
	0x73bebd3f,
	0xd272d446,
	0xe8213e80,
	0xd272d446,
	0x70eca2ca,
};
static const char ____version_ext_names[]
__used __section("__version_ext_names") =
	"iounmap\0"
	"pci_dev_put\0"
	"sscanf\0"
	"pci_get_domain_bus_and_slot\0"
	"ioremap\0"
	"pci_read_config_word\0"
	"pci_read_config_dword\0"
	"__stack_chk_fail\0"
	"param_ops_charp\0"
	"__fentry__\0"
	"_printk\0"
	"__x86_return_thunk\0"
	"module_layout\0"
;

MODULE_INFO(depends, "");


MODULE_INFO(srcversion, "19A423275984834307A24DB");
