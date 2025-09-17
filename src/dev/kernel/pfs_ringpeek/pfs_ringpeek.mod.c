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
	{ 0xcb8b6ec6, "kfree" },
	{ 0x092a35a2, "_copy_from_user" },
	{ 0x12ad300e, "iounmap" },
	{ 0x97dd6ca9, "ioremap" },
	{ 0xd272d446, "__stack_chk_fail" },
	{ 0x90a48d82, "__ubsan_handle_out_of_bounds" },
	{ 0x7d49d091, "debugfs_remove" },
	{ 0xd408da62, "misc_deregister" },
	{ 0xe8213e80, "_printk" },
	{ 0x4a7bd1cf, "pci_get_device" },
	{ 0xbd03ed67, "random_kmalloc_seed" },
	{ 0xa62b1cc9, "kmalloc_caches" },
	{ 0xd1f07d8f, "__kmalloc_cache_noprof" },
	{ 0x88fafe6b, "misc_register" },
	{ 0x662225ef, "debugfs_create_dir" },
	{ 0xe7d76335, "debugfs_create_file_full" },
	{ 0x9563cc48, "default_llseek" },
	{ 0xd272d446, "__fentry__" },
	{ 0xd272d446, "__x86_return_thunk" },
	{ 0xd710adbf, "__kmalloc_noprof" },
	{ 0xacac6336, "memcpy_fromio" },
	{ 0xa61fd7aa, "__check_object_size" },
	{ 0x092a35a2, "_copy_to_user" },
	{ 0xab006604, "module_layout" },
};

static const u32 ____version_ext_crcs[]
__used __section("__version_ext_crcs") = {
	0xcb8b6ec6,
	0x092a35a2,
	0x12ad300e,
	0x97dd6ca9,
	0xd272d446,
	0x90a48d82,
	0x7d49d091,
	0xd408da62,
	0xe8213e80,
	0x4a7bd1cf,
	0xbd03ed67,
	0xa62b1cc9,
	0xd1f07d8f,
	0x88fafe6b,
	0x662225ef,
	0xe7d76335,
	0x9563cc48,
	0xd272d446,
	0xd272d446,
	0xd710adbf,
	0xacac6336,
	0xa61fd7aa,
	0x092a35a2,
	0xab006604,
};
static const char ____version_ext_names[]
__used __section("__version_ext_names") =
	"kfree\0"
	"_copy_from_user\0"
	"iounmap\0"
	"ioremap\0"
	"__stack_chk_fail\0"
	"__ubsan_handle_out_of_bounds\0"
	"debugfs_remove\0"
	"misc_deregister\0"
	"_printk\0"
	"pci_get_device\0"
	"random_kmalloc_seed\0"
	"kmalloc_caches\0"
	"__kmalloc_cache_noprof\0"
	"misc_register\0"
	"debugfs_create_dir\0"
	"debugfs_create_file_full\0"
	"default_llseek\0"
	"__fentry__\0"
	"__x86_return_thunk\0"
	"__kmalloc_noprof\0"
	"memcpy_fromio\0"
	"__check_object_size\0"
	"_copy_to_user\0"
	"module_layout\0"
;

MODULE_INFO(depends, "");


MODULE_INFO(srcversion, "87BD4EC72394F234FF99E2A");
