#!/usr/bin/env python3
"""
Integrated Shell - Seamless execution across packet bridges
Combines PacketFS, OSv containers, and network CPU
"""
import os
import sys
import subprocess
from pathlib import Path
from packet_bridge import PacketBridge
from osv_executor import OSvExecutor
from distributed_cpu import DistributedCPU
from packet_vmkit import PacketVMKit
from fastfs import FastFS
import shlex
import asyncio

class IntegratedShell:
    def __init__(self):
        self.bridge = PacketBridge()
        self.osv = OSvExecutor()
        self.cpu = DistributedCPU()
        self.vmkit = PacketVMKit()
        self.fastfs = FastFS()
        self.cwd = Path.cwd()
        
    def start(self):
        """Start all integrated services"""
        print("Starting Integrated OS-Walk Shell...")
        self.bridge.start()
        print("Packet bridges active - network machines available as directories")
        
    def is_remote_path(self, path: str) -> bool:
        """Check if path is on remote machine via packet bridge"""
        return path.startswith("/net/")
    
    def get_remote_machine(self, path: str) -> str:
        """Extract machine name from /net/machine/path"""
        if not self.is_remote_path(path):
            return None
        parts = Path(path).parts
        return parts[2] if len(parts) > 2 else None
    
    def execute_command(self, command: str, args: list):
        """Execute command with intelligent routing"""
        full_cmd = f"{command} {' '.join(args)}"
        
        # Check if we're in a remote directory
        cwd_str = str(self.cwd)
        if self.is_remote_path(cwd_str):
            machine = self.get_remote_machine(cwd_str)
            print(f"Executing on {machine}: {full_cmd}")
            
            # Submit to OSv executor on target machine
            job_id = self.osv.submit_job(
                command=full_cmd,
                cwd=cwd_str,
                target_node=machine
            )
            
            # Wait for result and display
            result = self.osv.wait_for_job(job_id)
            if result.get("stdout"):
                print(result["stdout"], end="")
            if result.get("stderr"):
                print(result["stderr"], file=sys.stderr, end="")
            
            return result.get("returncode", 0)
        
        else:
            # Local execution - check if it's a compute-intensive task
            if command in ["python", "gcc", "make", "cargo", "npm"]:
                print(f"Offloading to network CPU: {full_cmd}")
                return self.cpu.execute_distributed(full_cmd)
            else:
                # Regular local execution
                try:
                    result = subprocess.run([command] + args, cwd=self.cwd)
                    return result.returncode
                except FileNotFoundError:
                    print(f"Command not found: {command}")
                    return 127
    
    def cmd_cd(self, args):
        """Change directory - works with packet bridges"""
        if not args:
            target = Path.home()
        else:
            target = Path(args[0])
            
        if not target.is_absolute():
            target = self.cwd / target
        
        try:
            # Resolve path (handles /net/machine paths)
            resolved = target.resolve()
            
            # For packet bridge paths, just update cwd
            if str(resolved).startswith("/net/"):
                self.cwd = resolved
                print(f"Changed to remote directory: {resolved}")
            else:
                os.chdir(resolved)
                self.cwd = Path.cwd()
                
        except (OSError, FileNotFoundError) as e:
            print(f"cd: {e}")
    
    def cmd_ls(self, args):
        """List directory - works with packet bridges"""
        if self.is_remote_path(str(self.cwd)):
            # Remote ls via OSv executor
            return self.execute_command("ls", args)
        else:
            # Local ls
            return self.execute_command("ls", args)
    
    def cmd_pwd(self, args):
        """Print working directory"""
        print(self.cwd)
    
    def cmd_bridges(self, args):
        """List active packet bridges"""
        bridges = self.bridge.list_bridges()
        if bridges:
            print("Active packet bridges:")
            for bridge in bridges:
                print(f"  /net/{bridge}")
        else:
            print("No active packet bridges")
    
    def cmd_vmkit(self, args):
        """AWESOMEIZED VMKit commands"""
        if not args:
            print("VMKIT - Available commands:")
            print("  vmkit create <name> [template] - Create packet VM")
            print("  vmkit start <name>            - Start packet VM")
            print("  vmkit stop <name>             - Stop packet VM")
            print("  vmkit list                    - List packet VMs")
            print("  vmkit status <name>           - Show VM status")
            return
        
        command = args[0]
        
        if command == "create" and len(args) >= 2:
            name = args[1]
            template = args[2] if len(args) > 2 else "ubuntu-24.04"
            self.vmkit.create_packet_vm(name, template)
            
        elif command == "start" and len(args) >= 2:
            name = args[1]
            self.vmkit.start_packet_vm(name)
            
        elif command == "stop" and len(args) >= 2:
            name = args[1]
            self.vmkit.stop_packet_vm(name)
            
        elif command == "list":
            self.vmkit.list_packet_vms()
            
        elif command == "status" and len(args) >= 2:
            name = args[1]
            self.vmkit.packet_vm_status(name)
            
        else:
            print(f"[ERR] Unknown vmkit command: {command}")
    
    def cmd_fastfs(self, args):
        """FastFS distributed filesystem commands"""
        if not args:
            print("FastFS - Ultra-fast distributed filesystem:")
            print("  fastfs write <path> <content> - Write file")
            print("  fastfs read <path>            - Read file")
            print("  fastfs list                   - List files")
            print("  fastfs stats                  - Show statistics")
            return
        
        command = args[0]
        
        if command == "write" and len(args) >= 3:
            path = args[1]
            content = " ".join(args[2:]).encode()
            
            async def write_file():
                await self.fastfs.write(path, content)
            
            asyncio.run(write_file())
            
        elif command == "read" and len(args) >= 2:
            path = args[1]
            
            async def read_file():
                data = await self.fastfs.read(path)
                if data:
                    print(data.decode())
                else:
                    print(f"File not found: {path}")
            
            asyncio.run(read_file())
            
        elif command == "list":
            files = self.fastfs.list_files()
            if files:
                print("FastFS files:")
                for f in files:
                    print(f"  {f}")
            else:
                print("No files in FastFS")
                
        elif command == "stats":
            stats = self.fastfs.stats()
            print(f"FastFS Statistics:")
            print(f"  Total files: {stats['total_files']}")
            print(f"  Total nodes: {stats['total_nodes']}")
            print(f"  Local cached: {stats['local_cached']}")
            print(f"  Node ID: {stats['node_id']}")
            
        else:
            print(f"[ERR] Unknown fastfs command: {command}")
    
    def run_shell(self):
        """Main shell loop"""
        self.start()
        
        print(f"OS-Walk Shell ready. Current directory: {self.cwd}")
        print("Try: cd /net/machine2, ls, or any command")
        
        while True:
            try:
                # Show current directory in prompt
                prompt = f"oswalk:{self.cwd}$ "
                line = input(prompt).strip()
                
                if not line:
                    continue
                    
                if line == "exit":
                    break
                
                # Parse command
                parts = shlex.split(line)
                command = parts[0]
                args = parts[1:]
                
                # Built-in commands
                if command == "cd":
                    self.cmd_cd(args)
                elif command == "pwd":
                    self.cmd_pwd(args)
                elif command == "bridges":
                    self.cmd_bridges(args)
                elif command == "vmkit":
                    self.cmd_vmkit(args)
                elif command == "fastfs":
                    self.cmd_fastfs(args)
                else:
                    # Execute command
                    self.execute_command(command, args)
                    
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                break
        
        print("Stopping OS-Walk Shell...")
        self.bridge.stop()

def main():
    shell = IntegratedShell()
    shell.run_shell()

if __name__ == "__main__":
    main()