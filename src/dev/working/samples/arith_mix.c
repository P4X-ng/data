#include <stdio.h>

volatile int A1 = 9;
volatile int B1 = 4;
volatile int C1 = 7;
volatile int D1 = 2;

int main(void) {
    int a = A1;
    int b = B1;
    int c = C1;
    int d = D1;
    // Compute (a + b) * (c - d) = (13) * (5) = 65
    int t1 = a + b;
    int t2 = c - d;
    int r = t1 * t2;
    return r;
}

