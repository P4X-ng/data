#!/usr/bin/env python3
"""
Packet VMKit - VMKit VMs running on PacketFS substrate
AWESOMEIZED virtual machines where everything is packets and math!
"""
import os
import subprocess
import sys
from pathlib import Path
import json
import uuid

class PacketVMKit:
    def __init__(self, vmkit_path="/home/punk/Projects/packetfs/full_apps/packetfs-infinity/VMKit"):
        self.vmkit_path = Path(vmkit_path)
        self.vmkit_bin = self.vmkit_path / "vmkit" / "vmkit" / "cli.py"
        
    def create_packet_vm(self, name: str, template: str = "ubuntu-24.04"):
        """Create VM on PacketFS substrate - AWESOMEIZED!"""
        vm_dir = Path(f"/pfs/vms/{name}")
        vm_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[VM] Creating packet VM: {name}")
        print(f"[SUBSTRATE] PacketFS (Network Packets)")
        print(f"[CPU] Still Metal (packets)")
        print(f"[STORAGE] Distributed Packet Blobs")
        
        # Mount PacketFS for VM storage
        mount_cmd = [
            "python", "-m", "packetfs.filesystem.pfsfs_mount",
            "--mount", str(vm_dir),
            "--blob-name", f"vmkit_{name}",
            "--blob-size", "21474836480",  # 20GB blob
            "--blob-seed", str(hash(name) % 65536),
            "--foreground", "false"
        ]
        
        try:
            subprocess.run(mount_cmd, check=True)
            print(f"[OK] PacketFS mounted at {vm_dir}")
        except Exception as e:
            print(f"[WARN] PacketFS mount failed: {e}")
        
        # Create VMKit VM in PacketFS directory
        vmkit_cmd = [
            "python", str(self.vmkit_bin),
            "create", name,
            "--template", template,
            "--storage-dir", str(vm_dir),
            "--memory", "2G",
            "--cpus", "2"
        ]
        
        print(f"[VMKIT] Creating VMKit VM: {' '.join(vmkit_cmd)}")
        
        try:
            result = subprocess.run(vmkit_cmd, cwd=vm_dir, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[OK] Packet VM created: {name}")
                print(f"[PATH] Location: {vm_dir}")
                print(f"[INFO] Every byte is now network packets!")
                
                # Save packet VM metadata
                metadata = {
                    "name": name,
                    "type": "PacketVMKit",
                    "substrate": "PacketFS",
                    "cpu_type": "Metal CPU (packets)",
                    "storage_type": "Distributed Packet Blobs",
                    "template": template,
                    "vm_dir": str(vm_dir),
                    "awesomeness_level": "MAXIMUM"
                }
                
                with open(vm_dir / "packet_vm.json", "w") as f:
                    json.dump(metadata, f, indent=2)
                    
            else:
                print(f"[ERR] VMKit creation failed: {result.stderr}")
                
        except Exception as e:
            print(f"[ERR] Error creating packet VM: {e}")
    
    def start_packet_vm(self, name: str):
        """Start packet VM - MAXIMUM AWESOMENESS!"""
        vm_dir = Path(f"/pfs/vms/{name}")
        
        print(f"[VM] Starting packet VM: {name}")
        print(f"[INIT] Initializing packet substrate...")
        print(f"[CPU] Booting metal CPU cores...")
        print(f"[NET] Establishing packet bridges...")
        
        # Start VMKit VM
        vmkit_cmd = [
            "python", str(self.vmkit_bin),
            "start", name,
            "--storage-dir", str(vm_dir)
        ]
        
        try:
            result = subprocess.run(vmkit_cmd, cwd=vm_dir)
            if result.returncode == 0:
                print(f"[OK] Packet VM {name} is running")
                print(f"[INFO] CPU instructions still metal (for now)")
                print(f"[INFO] Every disk I/O is now network packets!")
                print(f"[OK] VM startup complete")
            else:
                print(f"[ERR] Failed to start packet VM: {name}")
                
        except Exception as e:
            print(f"[ERR] Packet VM error: {e}")
    
    def stop_packet_vm(self, name: str):
        """Stop packet VM"""
        vm_dir = Path(f"/pfs/vms/{name}")
        
        print(f"[VM] Stopping packet VM: {name}")
        
        vmkit_cmd = [
            "python", str(self.vmkit_bin),
            "stop", name,
            "--storage-dir", str(vm_dir)
        ]
        
        subprocess.run(vmkit_cmd, cwd=vm_dir)
        print(f"[INFO] Packet VM {name} is stopped")
    
    def list_packet_vms(self):
        """List all packet VMs - AWESOMELY!"""
        vms_dir = Path("/pfs/vms")
        
        if not vms_dir.exists():
            print("No packet VMs found")
            return
        
        print("Packet VMs:")
        print("=" * 50)
        
        for vm_path in vms_dir.iterdir():
            if vm_path.is_dir():
                metadata_file = vm_path / "packet_vm.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    
                    print(f"* {metadata['name']}")
                    print(f"   Substrate: {metadata['substrate']}")
                    print(f"   CPU: {metadata['cpu_type']}")
                    print(f"   Storage: {metadata['storage_type']}")
                    print(f"   Awesomeness: {metadata['awesomeness_level']}")
                    print()
    
    def packet_vm_status(self, name: str):
        """Show packet VM status - AWESOMELY!"""
        vm_dir = Path(f"/pfs/vms/{name}")
        metadata_file = vm_dir / "packet_vm.json"
        
        if not metadata_file.exists():
            print(f"Packet VM {name} not found")
            return
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        print(f"Packet VM Status: {name}")
        print("=" * 40)
        print(f"Name: {metadata['name']}")
        print(f"Substrate: {metadata['substrate']}")
        print(f"CPU Type: {metadata['cpu_type']} (TODO: DNS-ify!)")
        print(f"Storage: {metadata['storage_type']}")
        print(f"Location: {metadata['vm_dir']}")
        print(f"Awesomeness: {metadata['awesomeness_level']}")
        
        # Check if VM is running via VMKit
        try:
            result = subprocess.run([
                "python", str(self.vmkit_bin),
                "status", name,
                "--storage-dir", str(vm_dir)
            ], capture_output=True, text=True, cwd=vm_dir)
            
            if "running" in result.stdout.lower():
                print("Status: RUNNING (Storage packets flowing, CPU still metal)")
            else:
                print("Status: STOPPED (All packets at rest)")
                
        except Exception as e:
            print(f"Status: UNKNOWN ({e})")

def main():
    if len(sys.argv) < 2:
        print("PACKET VMKIT - VMs")
        print("Usage: packet_vmkit.py <command> [args]")
        print("Commands:")
        print("  create <name> [template]  - Create packet VM")
        print("  start <name>             - Start packet VM")
        print("  stop <name>              - Stop packet VM")
        print("  list                     - List packet VMs")
        print("  status <name>            - Show VM status")
        return
    
    vmkit = PacketVMKit()
    command = sys.argv[1]
    
    if command == "create" and len(sys.argv) >= 3:
        name = sys.argv[2]
        template = sys.argv[3] if len(sys.argv) > 3 else "ubuntu-24.04"
        vmkit.create_packet_vm(name, template)
        
    elif command == "start" and len(sys.argv) >= 3:
        name = sys.argv[2]
        vmkit.start_packet_vm(name)
        
    elif command == "stop" and len(sys.argv) >= 3:
        name = sys.argv[2]
        vmkit.stop_packet_vm(name)
        
    elif command == "list":
        vmkit.list_packet_vms()
        
    elif command == "status" and len(sys.argv) >= 3:
        name = sys.argv[2]
        vmkit.packet_vm_status(name)
        
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()