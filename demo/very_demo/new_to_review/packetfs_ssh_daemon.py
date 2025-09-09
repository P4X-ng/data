#!/usr/bin/env python3
"""
PacketFS SSH Daemon - Handles SSH connections to PacketFS container
"""
import socket
import threading
import subprocess
import os

class PacketFSSSHDaemon:
    def __init__(self):
        self.port = 2200
        self.container_root = "/tmp/packetfs_container"
        
    def handle_client(self, client_socket, addr):
        """Handle SSH client connection"""
        try:
            # Send PacketFS SSH banner
            banner = b"SSH-2.0-PacketFS_SSH\r\n"
            client_socket.send(banner)
            
            # Simple command handler (not real SSH protocol)
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break
                    
                command = data.decode().strip()
                
                # Execute command in container via chroot
                result = self.execute_in_container(command)
                
                response = f"PacketFS> {result}\n".encode()
                client_socket.send(response)
                
        except Exception as e:
            print(f"SSH Error: {e}")
        finally:
            client_socket.close()
            
    def execute_in_container(self, command):
        """Execute command inside PacketFS container"""
        try:
            # Use chroot to execute in container
            full_command = f"chroot {self.container_root} /bin/bash -c '{command}'"
            result = subprocess.run(full_command, shell=True, 
                                  capture_output=True, text=True, timeout=10)
            return result.stdout + result.stderr
        except Exception as e:
            return f"Command failed: {e}"
            
    def start(self):
        """Start the SSH daemon"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('localhost', self.port))
        server.listen(5)
        
        print(f"PacketFS SSH Daemon listening on port {self.port}")
        
        while True:
            client, addr = server.accept()
            client_thread = threading.Thread(
                target=self.handle_client, 
                args=(client, addr)
            )
            client_thread.start()

if __name__ == "__main__":
    daemon = PacketFSSSHDaemon()
    daemon.start()
