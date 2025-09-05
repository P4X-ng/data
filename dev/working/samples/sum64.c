#include <stdio.h>

// 64 volatile globals
volatile int a01=1,a02=2,a03=3,a04=4,a05=5,a06=6,a07=7,a08=8,a09=9,a10=10;
volatile int a11=11,a12=12,a13=13,a14=14,a15=15,a16=16,a17=17,a18=18,a19=19,a20=20;
volatile int a21=21,a22=22,a23=23,a24=24,a25=25,a26=26,a27=27,a28=28,a29=29,a30=30;
volatile int a31=31,a32=32,a33=33,a34=34,a35=35,a36=36,a37=37,a38=38,a39=39,a40=40;
volatile int a41=41,a42=42,a43=43,a44=44,a45=45,a46=46,a47=47,a48=48,a49=49,a50=50;
volatile int a51=51,a52=52,a53=53,a54=54,a55=55,a56=56,a57=57,a58=58,a59=59,a60=60;
volatile int a61=61,a62=62,a63=63,a64=64;

int main(void) {
    int s = 0;
    s = s + a01; s = s + a02; s = s + a03; s = s + a04; s = s + a05; s = s + a06; s = s + a07; s = s + a08; s = s + a09; s = s + a10;
    s = s + a11; s = s + a12; s = s + a13; s = s + a14; s = s + a15; s = s + a16; s = s + a17; s = s + a18; s = s + a19; s = s + a20;
    s = s + a21; s = s + a22; s = s + a23; s = s + a24; s = s + a25; s = s + a26; s = s + a27; s = s + a28; s = s + a29; s = s + a30;
    s = s + a31; s = s + a32; s = s + a33; s = s + a34; s = s + a35; s = s + a36; s = s + a37; s = s + a38; s = s + a39; s = s + a40;
    s = s + a41; s = s + a42; s = s + a43; s = s + a44; s = s + a45; s = s + a46; s = s + a47; s = s + a48; s = s + a49; s = s + a50;
    s = s + a51; s = s + a52; s = s + a53; s = s + a54; s = s + a55; s = s + a56; s = s + a57; s = s + a58; s = s + a59; s = s + a60;
    s = s + a61; s = s + a62; s = s + a63; s = s + a64;
    return s; // sum 1..64 = 2080
}

