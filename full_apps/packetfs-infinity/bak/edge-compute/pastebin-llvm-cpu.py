#!/usr/bin/env python3
"""
PASTEBIN LLVM CPU: Execute LLVM IR using Pastebin as the execution engine! 🤯

Each LLVM instruction becomes a paste:
- LOAD = Create paste with loaded value
- ADD = Create paste with addition result  
- RET = Create paste with final return value

The paste URLs become our "registers" - we fetch previous results by reading pastes!

Example: add4.ll execution
1. Paste 1: %1 = load volatile i32, ptr @A  -> "5"
2. Paste 2: %2 = load volatile i32, ptr @B  -> "7" 
3. Paste 3: %5 = add nsw i32 %2, %1        -> "12" (reads Paste 1 & 2)
4. Paste 4: %6 = add nsw i32 %5, %3        -> "23" (reads Paste 3)
5. Paste 5: ret i32 %7                     -> "36" (final result)

PASTEBIN IS THE CPU! Each paste = one CPU cycle!
"""

import requests
import time
import json
import re
import hashlib
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

class PastebinLLVMCPU:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.registers: Dict[str, str] = {}  # SSA name -> paste URL
        self.globals: Dict[str, int] = {}    # Global variables
        self.pastes_created = []
        self.execution_trace = []
        
        # LLVM IR regex patterns (from ir_frontend.py)
        self.ADD_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*add\b.*?\bi32\s+([^,]+),\s+([^\s]+)")
        self.LOAD_VOL_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*load\s+volatile\s+i32,\s+ptr\s+@([A-Za-z0-9_]+)")
        self.RET_VAR_RE = re.compile(r"^\s*ret\s+i32\s+%([A-Za-z0-9_\.]+)\b")
        self.RET_CONST_RE = re.compile(r"^\s*ret\s+i32\s+(-?\d+)\b")
        self.GLOBAL_I32_RE = re.compile(r"^@([A-Za-z0-9_]+)\s*=\s*.*\bglobal\s+i32\s+(-?\d+)\b")
        
        print("🚀 PASTEBIN LLVM CPU INITIALIZED!")
        print("   Each LLVM instruction = one paste created")
        print("   Paste URLs = CPU registers")
        print("   Reading pastes = memory access")
    
    def create_paste(self, title: str, content: str) -> Optional[str]:
        """Create a paste (execute one CPU instruction)"""
        paste_data = {
            'api_dev_key': self.api_key,
            'api_option': 'paste',
            'api_paste_code': content,
            'api_paste_name': title,
            'api_paste_format': 'text',
            'api_paste_private': 1,  # Unlisted
            'api_paste_expire_date': '1H'
        }
        
        try:
            resp = requests.post('https://pastebin.com/api/api_post.php', data=paste_data)
            if resp.text.startswith('https://pastebin.com/'):
                url = resp.text.strip()
                self.pastes_created.append(url)
                return url
            else:
                print(f"   ❌ Paste failed: {resp.text}")
                return None
        except Exception as e:
            print(f"   ❌ Paste error: {e}")
            return None
    
    def read_paste_value(self, paste_url: str) -> Optional[int]:
        """Read a paste to get the computed value (memory access)"""
        try:
            # Extract paste ID from URL
            paste_id = paste_url.split('/')[-1]
            raw_url = f"https://pastebin.com/raw/{paste_id}"
            
            resp = requests.get(raw_url)
            if resp.status_code == 200:
                content = resp.text.strip()
                # Extract the result value from paste content
                for line in content.split('\n'):
                    if line.startswith('RESULT:'):
                        return int(line.split(':')[1].strip())
                # Fallback: try to parse as direct number
                try:
                    return int(content.split('\n')[0])
                except:
                    pass
            return None
        except Exception as e:
            print(f"   ❌ Failed to read paste {paste_url}: {e}")
            return None
    
    def resolve_operand(self, operand: str) -> int:
        """Resolve an operand (register or immediate)"""
        operand = operand.strip()
        
        if operand.startswith('%'):
            # SSA register - read from paste!
            reg_name = operand[1:]
            if reg_name not in self.registers:
                raise RuntimeError(f"Undefined register %{reg_name}")
            
            paste_url = self.registers[reg_name]
            value = self.read_paste_value(paste_url)
            if value is None:
                raise RuntimeError(f"Failed to read value from paste: {paste_url}")
            
            print(f"   📖 Read %{reg_name} = {value} from {paste_url}")
            return value
        else:
            # Immediate constant
            return int(operand) & 0xFFFFFFFF
    
    def execute_load(self, reg_name: str, global_name: str, instruction: str) -> bool:
        """Execute a load instruction by creating a paste"""
        if global_name not in self.globals:
            raise RuntimeError(f"Unknown global @{global_name}")
        
        value = self.globals[global_name]
        
        paste_content = f"""PASTEBIN LLVM CPU - LOAD INSTRUCTION
        
Instruction: {instruction}
Operation: LOAD
Register: %{reg_name}
Global: @{global_name}
RESULT: {value}

Memory Access:
- Loaded from global variable @{global_name}
- Value: {value} (0x{value:08x})
- Stored in register %{reg_name}

CPU State:
- Instruction executed successfully
- Register %{reg_name} now contains {value}
- Ready for next instruction

🤯 PASTEBIN IS THE CPU!
This paste represents one CPU load instruction!
"""
        
        paste_url = self.create_paste(f"LLVM-LOAD-%{reg_name}", paste_content)
        if paste_url:
            self.registers[reg_name] = paste_url
            self.execution_trace.append({
                'instruction': instruction,
                'operation': 'LOAD',
                'register': reg_name,
                'value': value,
                'paste_url': paste_url
            })
            print(f"   📝 LOAD %{reg_name} = {value} -> {paste_url}")
            return True
        return False
    
    def execute_add(self, reg_name: str, lhs: str, rhs: str, instruction: str) -> bool:
        """Execute an add instruction by creating a paste"""
        lhs_val = self.resolve_operand(lhs)
        rhs_val = self.resolve_operand(rhs)
        result = (lhs_val + rhs_val) & 0xFFFFFFFF
        
        paste_content = f"""PASTEBIN LLVM CPU - ADD INSTRUCTION

Instruction: {instruction}
Operation: ADD
Register: %{reg_name}
RESULT: {result}

Arithmetic:
- Left operand: {lhs} = {lhs_val}
- Right operand: {rhs} = {rhs_val}
- Addition: {lhs_val} + {rhs_val} = {result}
- Binary: {lhs_val:032b} + {rhs_val:032b} = {result:032b}

CPU State:
- ALU operation completed
- Register %{reg_name} now contains {result}
- Overflow handling: 32-bit wrap-around
- Ready for next instruction

Previous Values Retrieved From:
- {lhs}: {"paste" if lhs.startswith('%') else "immediate"}
- {rhs}: {"paste" if rhs.startswith('%') else "immediate"}

🚀 PASTEBIN ARITHMETIC UNIT!
This paste represents one CPU ADD instruction!
"""
        
        paste_url = self.create_paste(f"LLVM-ADD-%{reg_name}", paste_content)
        if paste_url:
            self.registers[reg_name] = paste_url
            self.execution_trace.append({
                'instruction': instruction,
                'operation': 'ADD',
                'register': reg_name,
                'operands': [lhs, rhs],
                'values': [lhs_val, rhs_val],
                'result': result,
                'paste_url': paste_url
            })
            print(f"   🧮 ADD %{reg_name} = {lhs_val} + {rhs_val} = {result} -> {paste_url}")
            return True
        return False
    
    def execute_return(self, operand: str, instruction: str) -> int:
        """Execute a return instruction by creating final result paste"""
        if operand.startswith('%'):
            # Return register value
            reg_name = operand[1:]
            result = self.resolve_operand(operand)
        else:
            # Return immediate
            result = int(operand) & 0xFFFFFFFF
        
        paste_content = f"""🏁 PASTEBIN LLVM CPU - PROGRAM COMPLETE!

Instruction: {instruction}
Operation: RETURN
FINAL RESULT: {result}

Program Execution Summary:
- Total instructions executed: {len(self.execution_trace)}
- Total pastes created: {len(self.pastes_created)}
- Final return value: {result}
- Return operand: {operand}

Execution Trace:
"""
        
        for i, trace in enumerate(self.execution_trace):
            paste_content += f"{i+1:2d}. {trace['operation']:4s} {trace['instruction'][:50]}...\n"
        
        paste_content += f"""
Register State (Paste URLs):
"""
        for reg, url in self.registers.items():
            paste_content += f"  %{reg}: {url}\n"
        
        paste_content += f"""
🎉 PROGRAM EXECUTION COMPLETE!
Result: {result}
Method: Distributed computation via Pastebin
Each paste = one CPU instruction executed!

PASTEBIN IS A TURING-COMPLETE CPU! 🤯
"""
        
        paste_url = self.create_paste(f"LLVM-RETURN-{result}", paste_content)
        if paste_url:
            self.execution_trace.append({
                'instruction': instruction,
                'operation': 'RETURN',
                'result': result,
                'paste_url': paste_url
            })
            print(f"   🏁 RETURN {result} -> {paste_url}")
        
        return result
    
    def execute_llvm_file(self, ll_file: str) -> Dict[str, Any]:
        """Execute an entire LLVM IR file using Pastebin as CPU!"""
        print(f"🚀 EXECUTING LLVM IR FILE: {ll_file}")
        print("=" * 60)
        
        comp_id = hashlib.md5(ll_file.encode()).hexdigest()[:8]
        start_time = time.time()
        
        # Parse globals first
        with open(ll_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                
                m_global = self.GLOBAL_I32_RE.match(line)
                if m_global:
                    global_name = m_global.group(1)
                    global_value = int(m_global.group(2)) & 0xFFFFFFFF
                    self.globals[global_name] = global_value
                    print(f"   🌍 Global @{global_name} = {global_value}")
        
        # Execute instructions
        with open(ll_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                
                # LOAD instruction
                m_load = self.LOAD_VOL_RE.match(line)
                if m_load:
                    reg_name = m_load.group(1)
                    global_name = m_load.group(2)
                    if not self.execute_load(reg_name, global_name, line):
                        raise RuntimeError(f"Failed to execute LOAD at line {line_num}")
                    time.sleep(1.2)  # Rate limiting
                    continue
                
                # ADD instruction
                m_add = self.ADD_RE.match(line)
                if m_add:
                    reg_name = m_add.group(1)
                    lhs = m_add.group(2)
                    rhs = m_add.group(3)
                    if not self.execute_add(reg_name, lhs, rhs, line):
                        raise RuntimeError(f"Failed to execute ADD at line {line_num}")
                    time.sleep(1.2)  # Rate limiting
                    continue
                
                # RETURN instruction
                m_ret_var = self.RET_VAR_RE.match(line)
                if m_ret_var:
                    operand = f"%{m_ret_var.group(1)}"
                    result = self.execute_return(operand, line)
                    break
                
                m_ret_const = self.RET_CONST_RE.match(line)
                if m_ret_const:
                    operand = m_ret_const.group(1)
                    result = self.execute_return(operand, line)
                    break
        
        duration = time.time() - start_time
        
        return {
            'computation_id': comp_id,
            'file': ll_file,
            'result': result,
            'instructions_executed': len(self.execution_trace),
            'pastes_created': len(self.pastes_created),
            'paste_urls': self.pastes_created,
            'execution_trace': self.execution_trace,
            'duration': duration,
            'instructions_per_second': len(self.execution_trace) / duration if duration > 0 else 0
        }

def demo_pastebin_llvm():
    """Demo: Execute LLVM IR using Pastebin as CPU!"""
    
    api_key = "YOUR_PASTEBIN_API_KEY"
    
    if api_key == "YOUR_PASTEBIN_API_KEY":
        print("❌ Need real Pastebin API key!")
        print("   1. Get API key from https://pastebin.com/doc_api")
        print("   2. Update api_key in this script")
        print("\n🤯 WHAT THIS WILL DO:")
        print("   • Parse LLVM IR instructions")
        print("   • Execute each instruction as a paste")
        print("   • Use paste URLs as CPU registers")
        print("   • Read previous pastes for operand values")
        print("   • Create final result paste")
        print("   • PASTEBIN BECOMES A TURING-COMPLETE CPU!")
        return
    
    cpu = PastebinLLVMCPU(api_key)
    
    # Example: execute add4.ll
    ll_file = "/path/to/add4.ll"  # Update with real path
    
    if not os.path.exists(ll_file):
        print(f"❌ LLVM IR file not found: {ll_file}")
        print("   Create add4.ll or update the path")
        return
    
    try:
        result = cpu.execute_llvm_file(ll_file)
        
        print(f"\n🎉 PASTEBIN LLVM EXECUTION COMPLETE!")
        print(f"   File: {result['file']}")
        print(f"   Result: {result['result']}")
        print(f"   Instructions: {result['instructions_executed']}")
        print(f"   Pastes created: {result['pastes_created']}")
        print(f"   Duration: {result['duration']:.2f}s")
        print(f"   Speed: {result['instructions_per_second']:.2f} instructions/sec")
        
        print(f"\n📝 CHECK YOUR PASTES:")
        for i, url in enumerate(result['paste_urls']):
            print(f"   {i+1:2d}. {url}")
        
        print(f"\n🤯 PASTEBIN IS NOW A CPU!")
        print(f"   • Each paste = one CPU instruction")
        print(f"   • Paste URLs = CPU registers")
        print(f"   • Reading pastes = memory access")
        print(f"   • TURING COMPLETE COMPUTATION!")
        
    except Exception as e:
        print(f"❌ Execution failed: {e}")

if __name__ == '__main__':
    demo_pastebin_llvm()