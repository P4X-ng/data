#!/usr/bin/env python3
"""
Network Assembly Language - Write programs that execute on internet infrastructure
"""

import asyncio
from instruction_proxy import NetworkCPU

class NetworkAssembler:
    def __init__(self):
        self.labels = {}
        self.program = []
    
    def parse(self, asm_code: str) -> list:
        """Parse assembly code into instruction list"""
        lines = [line.strip() for line in asm_code.split('\n') if line.strip()]
        program = []
        
        for i, line in enumerate(lines):
            if line.startswith(';'):  # Comment
                continue
                
            if line.endswith(':'):  # Label
                self.labels[line[:-1]] = len(program)
                continue
            
            # Parse instruction
            parts = line.split()
            op = parts[0].upper()
            
            if op in ['ADD', 'SUB', 'MUL', 'DIV']:
                src, dst = parts[1].split(',')
                program.append({"op": op, "src": src.strip(), "dst": dst.strip()})
                
            elif op == 'MOV':
                src, dst = parts[1].split(',')
                src = src.strip()
                dst = dst.strip()
                
                # Handle immediate values
                if src.isdigit():
                    src = int(src)
                    
                program.append({"op": op, "src": src, "dst": dst})
                
            elif op == 'CMP':
                src, dst = parts[1].split(',')
                program.append({"op": op, "src": src.strip(), "dst": dst.strip()})
        
        return program

async def run_network_program(asm_code: str):
    """Compile and run network assembly program"""
    assembler = NetworkAssembler()
    program = assembler.parse(asm_code)
    
    cpu = NetworkCPU()
    
    print("🌐 Network Assembly Execution")
    print("=" * 40)
    print("Program:")
    for i, instr in enumerate(program):
        print(f"  {i:2}: {instr}")
    print()
    
    await cpu.execute_program(program)
    
    print("Results:")
    print(f"  Registers: {cpu.registers}")
    print(f"  Flags: {cpu.flags}")
    print(f"  Cycles: {cpu.cycles}")
    return cpu

# Example programs
FIBONACCI_ASM = """
; Fibonacci using network infrastructure
MOV 0, AX    ; F(0) = 0
MOV 1, BX    ; F(1) = 1
MOV 10, CX   ; Counter

fib_loop:
ADD AX, BX   ; BX = F(n-1) + F(n-2)
MOV BX, DX   ; Save old BX
MOV AX, BX   ; AX = old BX
MOV DX, AX   ; BX = new sum
SUB 1, CX    ; Decrement counter
CMP 0, CX    ; Check if done
"""

FACTORIAL_ASM = """
; Factorial using DNS and HTTP
MOV 5, AX    ; Calculate 5!
MOV 1, BX    ; Result accumulator

fact_loop:
MUL AX, BX   ; BX *= AX
SUB 1, AX    ; AX--
CMP 0, AX    ; Check if done
"""

SIMPLE_MATH_ASM = """
; Simple math demo
MOV 42, AX
MOV 13, BX
ADD BX, AX   ; AX = 42 + 13 = 55
SUB 5, AX    ; AX = 55 - 5 = 50
MUL 2, AX    ; AX = 50 * 2 = 100
DIV 4, AX    ; AX = 100 / 4 = 25
CMP 25, AX   ; Should set ZF=1
"""

async def demo():
    print("🚀 Network Assembly Language Demo\n")
    
    programs = [
        ("Simple Math", SIMPLE_MATH_ASM),
        ("Factorial", FACTORIAL_ASM),
    ]
    
    for name, code in programs:
        print(f"📝 Running: {name}")
        print("-" * 30)
        cpu = await run_network_program(code)
        print(f"Final AX: {cpu.registers['AX']}")
        print()

if __name__ == "__main__":
    asyncio.run(demo())