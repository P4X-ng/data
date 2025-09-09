
; Fibonacci sequence in assembly
; Perfect for PacketFS packet-based execution
section .text
    global _start

_start:
    mov rax, 0      ; First Fibonacci number
    mov rbx, 1      ; Second Fibonacci number
    mov rcx, 10     ; Counter for 10 iterations
    
fib_loop:
    add rax, rbx    ; rax = rax + rbx
    xchg rax, rbx   ; Swap rax and rbx
    dec rcx         ; Decrement counter
    jnz fib_loop    ; Jump if not zero
    
    ; Exit
    mov rax, 60     ; sys_exit
    mov rdi, 0      ; Exit status
    syscall
