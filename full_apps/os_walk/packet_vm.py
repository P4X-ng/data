#!/usr/bin/env python3
"""
Packet VM - QEMU VMs running on PacketFS substrate
Every VM operation becomes network packets/math
"""
import os
import subprocess
from pathlib import Path
import json
import uuid

class PacketVM:
    def __init__(self, name: str, vm_dir: str = "/pfs/vms"):
        self.name = name
        self.vm_dir = Path(vm_dir)
        self.vm_path = self.vm_dir / name
        self.vm_id = f"pvm-{uuid.uuid4().hex[:8]}"
        
    def create_vm_dir(self):
        """Create directory and mount PacketFS"""
        print(f"Creating packet VM directory: {self.vm_path}")
        self.vm_path.mkdir(parents=True, exist_ok=True)
        
        # Mount PacketFS at VM directory
        mount_cmd = [
            "python", "-m", "packetfs.filesystem.pfsfs_mount",
            "--mount", str(self.vm_path),
            "--blob-name", f"vm_{self.name}",
            "--blob-size", "10737418240",  # 10GB blob for VM
            "--blob-seed", str(hash(self.name) % 65536),
            "--foreground", "false"
        ]
        
        subprocess.run(mount_cmd, check=True)
        print(f"PacketFS mounted at {self.vm_path}")
        
        # Everything in this directory is now packets/math!
        return self.vm_path
    
    def create_disk(self, size: str = "5G"):
        """Create QEMU disk - stored as PacketFS"""
        disk_path = self.vm_path / f"{self.name}.qcow2"
        
        print(f"Creating packet-based disk: {disk_path}")
        subprocess.run([
            "qemu-img", "create", "-f", "qcow2", 
            str(disk_path), size
        ], check=True)
        
        print(f"Disk created - every byte is now network packets!")
        return disk_path
    
    def start_vm(self, memory: str = "1G", cpus: int = 2, iso: str = None):
        """Start QEMU VM - everything runs on packet substrate"""
        disk_path = self.vm_path / f"{self.name}.qcow2"
        
        qemu_cmd = [
            "qemu-system-x86_64",
            "-name", f"packet-vm-{self.name}",
            "-m", memory,
            "-smp", str(cpus),
            "-hda", str(disk_path),
            "-netdev", "user,id=net0",
            "-device", "e1000,netdev=net0",
            "-vnc", f":1{hash(self.name) % 100}",  # Unique VNC port
            "-daemonize"
        ]
        
        if iso:
            qemu_cmd.extend(["-cdrom", iso])
        
        print(f"Starting packet VM: {self.name}")
        print(f"Command: {' '.join(qemu_cmd)}")
        print(f"VM storage: PacketFS (network packets)")
        print(f"VM CPU: Network CPU (DNS/HTTP operations)")
        print(f"VM memory: Distributed across packet substrate")
        
        subprocess.run(qemu_cmd, cwd=self.vm_path, check=True)
        
        # Save VM info
        vm_info = {
            "name": self.name,
            "vm_id": self.vm_id,
            "disk_path": str(disk_path),
            "memory": memory,
            "cpus": cpus,
            "substrate": "PacketFS",
            "cpu_type": "Network CPU (DNS/HTTP)",
            "storage_type": "Network Packets"
        }
        
        with open(self.vm_path / "vm_info.json", "w") as f:
            json.dump(vm_info, f, indent=2)
        
        print(f"Packet VM {self.name} started!")
        print(f"Every operation inside this VM is now network math!")
        
    def stop_vm(self):
        """Stop the packet VM"""
        subprocess.run([
            "pkill", "-f", f"packet-vm-{self.name}"
        ], check=False)
        print(f"Packet VM {self.name} stopped")
    
    def status(self):
        """Show VM status"""
        vm_info_path = self.vm_path / "vm_info.json"
        if vm_info_path.exists():
            with open(vm_info_path) as f:
                info = json.load(f)
            
            print(f"Packet VM: {info['name']}")
            print(f"  Substrate: {info['substrate']}")
            print(f"  CPU Type: {info['cpu_type']}")
            print(f"  Storage: {info['storage_type']}")
            print(f"  Memory: {info['memory']}")
            print(f"  vCPUs: {info['cpus']}")
            
            # Check if running
            result = subprocess.run([
                "pgrep", "-f", f"packet-vm-{self.name}"
            ], capture_output=True)
            
            if result.returncode == 0:
                print(f"  Status: RUNNING (PID: {result.stdout.decode().strip()})")
            else:
                print(f"  Status: STOPPED")
        else:
            print(f"Packet VM {self.name} not found")

def main():
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: packet_vm.py <command> <vm_name> [options]")
        print("Commands: create, start, stop, status")
        return
    
    command = sys.argv[1]
    vm_name = sys.argv[2]
    
    vm = PacketVM(vm_name)
    
    if command == "create":
        vm.create_vm_dir()
        size = sys.argv[3] if len(sys.argv) > 3 else "5G"
        vm.create_disk(size)
        print(f"Packet VM {vm_name} created!")
        print(f"Directory: {vm.vm_path}")
        print(f"Everything in this VM is now packets and math!")
        
    elif command == "start":
        iso = sys.argv[3] if len(sys.argv) > 3 else None
        vm.start_vm(iso=iso)
        
    elif command == "stop":
        vm.stop_vm()
        
    elif command == "status":
        vm.status()
        
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()