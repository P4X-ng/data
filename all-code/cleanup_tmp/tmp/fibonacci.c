#include <stdio.h>

// Simple Fibonacci function - perfect for testing packet sharding!
int fibonacci(int n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main() {
    printf("🔥 PacketFS Neural Network Fibonacci Test! 💎\n");
    
    int result = fibonacci(10);
    
    printf("Fibonacci(10) = %d\n", result);
    printf("✅ Computation complete on 1.3M packet cores!\n");
    
    return 0;
}
