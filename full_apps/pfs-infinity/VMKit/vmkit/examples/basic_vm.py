#!/usr/bin/env python3
"""
Basic VM creation example using VMKit
"""

from vmkit import SecureVM, CloudImage, quick_config

def create_basic_vm():
    """Create a basic Ubuntu VM with cloud-init"""
    
    # Configure cloud-init
    cloud_init = quick_config(
        vm_name="example-vm",
        username="ubuntu",
        packages=["curl", "wget", "htop"]
    )
    
    # Set up cloud image
    image = CloudImage(
        path="/path/to/ubuntu-22.04-server-cloudimg-amd64.img",
        cloud_init_config=cloud_init
    )
    
    # Create VM
    vm = SecureVM(
        name="example-vm",
        memory="4G",
        cpus=2,
        image=image,
        secure_boot=True
    )
    
    # Create and start
    vm.create()
    vm.start()
    
    print(f"VM created: {vm}")
    print("Connect with: vmkit console example-vm")

if __name__ == "__main__":
    create_basic_vm()