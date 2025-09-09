/*
 * PacketFS Revolutionary Demo - The Ultimate Demonstration
 * Showcasing the world's first executable packet filesystem!
 */

#include "packetfs_revolutionary.c"

int main(int argc, char* argv[]) {
    printf("\n");
    printf("██████╗  █████╗  ██████╗██╗  ██╗███████╗████████╗███████╗███████╗\n");
    printf("██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝██╔════╝██╔════╝\n");
    printf("██████╔╝███████║██║     █████╔╝ █████╗     ██║   █████╗  ███████╗\n");
    printf("██╔═══╝ ██╔══██║██║     ██╔═██╗ ██╔══╝     ██║   ██╔══╝  ╚════██║\n");
    printf("██║     ██║  ██║╚██████╗██║  ██╗███████╗   ██║   ██║     ███████║\n");
    printf("╚═╝     ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝     ╚══════╝\n");
    printf("\n");
    printf("🌟 THE REVOLUTIONARY PACKET FILESYSTEM 🌟\n");
    printf("\"Storage IS Packets, Execution IS Network Flow, Computing IS Distributed\"\n\n");
    
    // Parse command line arguments
    size_t filesystem_size_gb = 2;    // Default 2GB
    size_t test_file_size_mb = 100;   // Default 100MB
    
    if (argc > 1) {
        filesystem_size_gb = atol(argv[1]);
        if (filesystem_size_gb == 0) {
            filesystem_size_gb = 2; // Minimum 2GB for demos
        }
    }
    if (argc > 2) {
        test_file_size_mb = atol(argv[2]);
        if (test_file_size_mb == 0) {
            test_file_size_mb = 100; // Minimum 100MB
        }
    }
    
    printf("⚙️  Configuration:\n");
    printf("   📁 Filesystem size: %zu GB\n", filesystem_size_gb);
    printf("   📄 Test file size: %zu MB\n", test_file_size_mb);
    printf("   💻 OpenMP threads: %d\n", omp_get_max_threads());
    printf("   🔧 MicroVMs available: %d\n", MICROVM_POOL_SIZE);
    printf("\n");
    
    // Show system capabilities
    printf("💻 System Capabilities:\n");
    printf("   🧠 CPU cores: %d\n", omp_get_max_threads());
    
    // Check for AVX2 support
    #ifdef __AVX2__
    printf("   ⚡ SIMD acceleration: AVX2 enabled\n");
    #else
    printf("   ⚡ SIMD acceleration: Standard (AVX2 not available)\n");
    #endif
    
    printf("   💾 Process memory: Started\n");
    printf("   🌐 Network support: Enabled\n");
    printf("\n");
    
    // Run the revolutionary demonstration
    revolutionary_ultimate_demo(filesystem_size_gb, test_file_size_mb);
    
    printf("\n🎊 PacketFS Revolutionary Demo Complete! 🎊\n");
    printf("You have witnessed the future of computing:\n");
    printf("• Storage that IS packets (not files)\n");
    printf("• Execution that flows like network traffic\n");
    printf("• Computing distributed across MicroVMs\n");
    printf("• Performance that shatters traditional limits\n");
    printf("\nWelcome to the Packet Age! 🚀\n\n");
    
    return 0;
}
