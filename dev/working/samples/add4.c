#include <stdio.h>

// Simple, deterministic program that preserves runtime adds under -O3
// Use volatile globals to prevent constant-folding.
volatile int A = 5;
volatile int B = 7;
volatile int Cc = 11;
volatile int Dd = 13;

static int add4(void) {
    int a = A;
    int b = B;
    int c = Cc;
    int d = Dd;
    return a + b + c + d; // 36
}

int main(void) {
    int r = add4();
    return r;
}

