#!/usr/bin/env python3
"""
Test VMKit with Ubuntu cloud image
"""

import sys
import os
sys.path.insert(0, '/home/punk/Projects/edk2-bootkit-defense/PhoenixGuard')

from vmkit import SecureVM, CloudImage, CloudInitConfig, ssh_only_config

def test_vmkit():
    print("🧪 Testing VMKit with Ubuntu 24.04 cloud image...")
    
    # Use the Ubuntu cloud image copy (to avoid file locking issues)
    image_path = "/home/punk/Projects/edk2-bootkit-defense/PhoenixGuard/testvm-image.qcow2"
    
    print(f"📀 Using image: {image_path}")
    
    # Create cloud-init config with SSH keys only
    print("🔧 Creating cloud-init configuration...")
    cloud_init = ssh_only_config("testvm")
    
    # Create cloud image with cloud-init
    image = CloudImage(image_path, cloud_init_config=cloud_init)
    
    # Create VM
    print("🖥️  Creating SecureVM...")
    vm = SecureVM(
        name="testvm",
        memory="2G",  # Start small
        cpus=2,
        image=image,
        secure_boot=True,
        graphics="none"  # Headless for now
    )
    
    # Show info before creation
    print("\n📋 VM Configuration:")
    print(f"  Name: {vm.name}")
    print(f"  Memory: {vm.memory_mb}MB")
    print(f"  CPUs: {vm.cpus}")
    print(f"  Secure Boot: {vm.secure_boot}")
    print(f"  Graphics: {vm.graphics}")
    print(f"  OVMF Code: {vm.ovmf_code}")
    print(f"  NVRAM: {vm.nvram_path}")
    
    # Check if VM already exists
    if vm.is_defined():
        print(f"⚠️  VM '{vm.name}' already exists. Destroying first...")
        vm.destroy()
    
    try:
        # Create the VM
        print("\n🚀 Creating VM...")
        vm.create()
        print("✅ VM created successfully!")
        
        # Show VM info
        print("\n📊 VM Info:")
        info = vm.info()
        for key, value in info.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        # Start the VM
        print("\n▶️  Starting VM...")
        vm.start()
        print("✅ VM started successfully!")
        
        # Show final status
        print(f"\n🎉 VM '{vm.name}' is now running!")
        print(f"   State: {'running' if vm.is_active() else 'stopped'}")
        print(f"   Connect: sudo vmkit console {vm.name}")
        print(f"   Or: sudo virsh console {vm.name}")
        
        # Don't auto-destroy for manual testing
        print(f"\n💡 To stop and destroy the VM later:")
        print(f"   python3 -c \"")
        print(f"import sys; sys.path.insert(0, '.')") 
        print(f"from vmkit import SecureVM")
        print(f"vm = SecureVM('{vm.name}')")
        print(f"vm.stop().destroy()")
        print(f"print('VM destroyed')\"")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_vmkit()
    sys.exit(0 if success else 1)
