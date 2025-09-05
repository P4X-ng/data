#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "llvm_packet_compiler.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <file.ll>\n", argv[0]);
        return 2;
    }

    const char *path = argv[1];

    // Minimal compiler object; zero-init is sufficient for parser
    llvm_packet_compiler_t compiler;
    memset(&compiler, 0, sizeof(compiler));

    int rc = llvm_parse_ir_file(&compiler, path);
    if (rc != 0) {
        fprintf(stderr, "Failed to parse LLVM IR file: %s\n", path);
        return 1;
    }

    // Print a stable summary suitable for tests
    llvm_print_module_info(compiler.module);

    return 0;
}

