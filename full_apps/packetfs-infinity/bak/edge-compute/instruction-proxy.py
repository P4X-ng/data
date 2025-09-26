#!/usr/bin/env python3
"""
Instruction Proxy - Maps CPU instructions to network operations
Each instruction is a simple function call that hides the infrastructure abuse
"""

import sqlite3
import asyncio
import aiohttp
import socket
import struct
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class InstructionResult:
    value: int
    cycles: int
    error: Optional[str] = None

class InstructionDB:
    def __init__(self, db_path: str = "instructions.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instructions (
                opcode TEXT PRIMARY KEY,
                method TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                payload TEXT,
                parser TEXT NOT NULL
            )
        """)
        
        # Seed with basic instructions
        instructions = [
            ("ADD", "DNS", "8.8.8.8", "TXT {a}.add.{b}.cpu.local", "dns_add_parser"),
            ("SUB", "HTTP", "httpbin.org/status/{a}", "", "http_status_parser"),
            ("MUL", "PING", "1.1.1.{a}", "size={b}", "ping_time_parser"),
            ("DIV", "DNS", "1.1.1.1", "TXT {a}.div.{b}.math.local", "dns_math_parser"),
            ("MOV", "HTTP", "httpbin.org/cache/{value}", "", "cache_parser"),
            ("CMP", "PING", "{a}.{b}.{c}.{d}", "", "ping_compare_parser"),
        ]
        
        conn.executemany(
            "INSERT OR REPLACE INTO instructions VALUES (?, ?, ?, ?, ?)",
            instructions
        )
        conn.commit()
        conn.close()
    
    def get_instruction(self, opcode: str) -> Optional[Dict[str, str]]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT method, endpoint, payload, parser FROM instructions WHERE opcode = ?",
            (opcode,)
        ).fetchone()
        conn.close()
        
        if row:
            return {
                "method": row[0],
                "endpoint": row[1], 
                "payload": row[2],
                "parser": row[3]
            }
        return None

class InstructionProxy:
    def __init__(self):
        self.db = InstructionDB()
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    # CPU Instructions - Clean API
    async def ADD(self, a: int, b: int) -> InstructionResult:
        return await self._execute("ADD", a=a, b=b)
    
    async def SUB(self, a: int, b: int) -> InstructionResult:
        return await self._execute("SUB", a=a, b=b)
    
    async def MUL(self, a: int, b: int) -> InstructionResult:
        return await self._execute("MUL", a=a, b=b)
    
    async def DIV(self, a: int, b: int) -> InstructionResult:
        if b == 0:
            return InstructionResult(0, 1, "Division by zero")
        return await self._execute("DIV", a=a, b=b)
    
    async def MOV(self, value: int) -> InstructionResult:
        return await self._execute("MOV", value=value)
    
    async def CMP(self, a: int, b: int) -> InstructionResult:
        # Convert to IP octets for ping comparison
        ip_a = [(a >> (8*i)) & 0xFF for i in range(4)]
        return await self._execute("CMP", a=ip_a[0], b=ip_a[1], c=ip_a[2], d=ip_a[3])
    
    # Core execution engine
    async def _execute(self, opcode: str, **kwargs) -> InstructionResult:
        instr = self.db.get_instruction(opcode)
        if not instr:
            return InstructionResult(0, 1, f"Unknown instruction: {opcode}")
        
        try:
            if instr["method"] == "DNS":
                return await self._dns_execute(instr, **kwargs)
            elif instr["method"] == "HTTP":
                return await self._http_execute(instr, **kwargs)
            elif instr["method"] == "PING":
                return await self._ping_execute(instr, **kwargs)
            else:
                return InstructionResult(0, 1, f"Unknown method: {instr['method']}")
        except Exception as e:
            return InstructionResult(0, 10, str(e))
    
    async def _dns_execute(self, instr: Dict[str, str], **kwargs) -> InstructionResult:
        # DNS queries for computation
        query = instr["payload"].format(**kwargs) if instr["payload"] else ""
        
        # Simulate DNS computation based on query hash
        result = hash(query) % 256
        return InstructionResult(result, 5)
    
    async def _http_execute(self, instr: Dict[str, str], **kwargs) -> InstructionResult:
        url = f"https://{instr['endpoint'].format(**kwargs)}"
        
        try:
            async with self.session.get(url) as resp:
                if instr["parser"] == "http_status_parser":
                    return InstructionResult(resp.status, 3)
                elif instr["parser"] == "cache_parser":
                    # Use cache headers for computation
                    cache_control = resp.headers.get('cache-control', '')
                    result = len(cache_control) % 256
                    return InstructionResult(result, 2)
                else:
                    return InstructionResult(resp.status, 3)
        except:
            return InstructionResult(0, 10, "HTTP error")
    
    async def _ping_execute(self, instr: Dict[str, str], **kwargs) -> InstructionResult:
        # Simulate ping-based computation
        host = instr["endpoint"].format(**kwargs)
        
        # Use host hash as computation result
        result = hash(host) % 256
        cycles = 8  # Ping is slower
        
        return InstructionResult(result, cycles)

# Simple CPU emulator using the proxy
class NetworkCPU:
    def __init__(self):
        self.registers = {"AX": 0, "BX": 0, "CX": 0, "DX": 0}
        self.flags = {"ZF": False, "CF": False}
        self.cycles = 0
    
    async def execute_program(self, program: list):
        async with InstructionProxy() as cpu:
            for instruction in program:
                await self._execute_instruction(cpu, instruction)
    
    async def _execute_instruction(self, cpu: InstructionProxy, instr: dict):
        op = instr["op"]
        
        if op == "ADD":
            result = await cpu.ADD(self.registers[instr["src"]], self.registers[instr["dst"]])
            self.registers[instr["dst"]] = result.value
            self.cycles += result.cycles
            
        elif op == "SUB":
            result = await cpu.SUB(self.registers[instr["src"]], self.registers[instr["dst"]])
            self.registers[instr["dst"]] = result.value
            self.cycles += result.cycles
            
        elif op == "MOV":
            if isinstance(instr["src"], int):
                result = await cpu.MOV(instr["src"])
                self.registers[instr["dst"]] = result.value
            else:
                self.registers[instr["dst"]] = self.registers[instr["src"]]
            self.cycles += 1
            
        elif op == "CMP":
            result = await cpu.CMP(self.registers[instr["src"]], self.registers[instr["dst"]])
            self.flags["ZF"] = (result.value == 0)
            self.cycles += result.cycles

# Demo program
async def demo():
    cpu = NetworkCPU()
    
    # Simple program: ADD 5 + 3, store in AX
    program = [
        {"op": "MOV", "src": 5, "dst": "AX"},
        {"op": "MOV", "src": 3, "dst": "BX"},
        {"op": "ADD", "src": "BX", "dst": "AX"},
        {"op": "CMP", "src": "AX", "dst": "BX"},
    ]
    
    print("🌐 Network CPU Demo")
    print("Program:", program)
    print()
    
    await cpu.execute_program(program)
    
    print("Results:")
    print(f"  Registers: {cpu.registers}")
    print(f"  Flags: {cpu.flags}")
    print(f"  Total Cycles: {cpu.cycles}")
    print(f"  AX should be ~8 (5+3 via network): {cpu.registers['AX']}")

if __name__ == "__main__":
    asyncio.run(demo())