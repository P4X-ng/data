#!/usr/bin/env python3
"""
👁️🔄 QUANTUM DIRECTORY WATCHER 🔄👁️
Auto-switches shell mode when entering/leaving quantum directory
"""

import os
import sys
import time
import subprocess
import threading
import signal
from pathlib import Path

class QuantumDirectoryWatcher:
    def __init__(self):
        self.quantum_dir = Path("/mnt/packetfs_quantum")
        self.quantum_shell = Path("/.pfs2/quantum_packetfs_infinite_shell.py")
        self.check_interval = 1  # Check every second
        self.current_mode = "normal"
        self.quantum_process = None
        self.running = True
        
    def get_current_directory(self):
        """Get the current working directory of the shell"""
        try:
            # Try to find the current directory from various sources
            pwd = os.environ.get('PWD', os.getcwd())
            return Path(pwd).resolve()
        except:
            return Path.cwd()
            
    def is_in_quantum_zone(self):
        """Check if current directory is in quantum zone"""
        try:
            current = self.get_current_directory()
            return current == self.quantum_dir or self.quantum_dir in current.parents
        except:
            return False
            
    def enter_quantum_mode(self):
        """Switch to quantum shell mode"""
        if self.current_mode == "quantum":
            return
            
        print("🚀 ENTERING QUANTUM MODE! 🚀")
        print("🌌 Reality distortion field activated!")
        print("⚡ Infinite compute power engaged!")
        print("💫 Type 'exit' to return to normal mode")
        print()
        
        self.current_mode = "quantum" 
        
        # Launch quantum shell
        try:
            self.quantum_process = subprocess.Popen([
                sys.executable, str(self.quantum_shell)
            ], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
            
        except Exception as e:
            print(f"❌ Failed to start quantum shell: {e}")
            
    def exit_quantum_mode(self):
        """Switch back to normal shell mode"""
        if self.current_mode == "normal":
            return
            
        print("\n🔄 EXITING QUANTUM MODE...")
        print("📉 Reality distortion field deactivated")  
        print("😴 Returning to boring normal computing")
        print()
        
        self.current_mode = "normal"
        
        # Kill quantum shell if running
        if self.quantum_process and self.quantum_process.poll() is None:
            try:
                self.quantum_process.terminate()
                self.quantum_process.wait(timeout=2)
            except:
                try:
                    self.quantum_process.kill()
                except:
                    pass
        self.quantum_process = None
        
    def watch_directory(self):
        """Main watching loop"""
        print("👁️  QUANTUM DIRECTORY WATCHER ACTIVE")
        print(f"🎯 Monitoring: {self.quantum_dir}")
        print("🔄 Auto-switch enabled!")
        print()
        
        last_state = False
        
        while self.running:
            try:
                in_quantum = self.is_in_quantum_zone()
                
                if in_quantum and not last_state:
                    # Entering quantum zone
                    self.enter_quantum_mode()
                elif not in_quantum and last_state:
                    # Leaving quantum zone  
                    self.exit_quantum_mode()
                    
                last_state = in_quantum
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n👁️  Directory watcher stopping...")
                break
            except Exception as e:
                print(f"❌ Watcher error: {e}")
                time.sleep(self.check_interval)
                
        self.exit_quantum_mode()
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.running = False
        self.exit_quantum_mode()
        
if __name__ == "__main__":
    watcher = QuantumDirectoryWatcher()
    
    # Handle signals
    signal.signal(signal.SIGINT, watcher.signal_handler)
    signal.signal(signal.SIGTERM, watcher.signal_handler)
    
    watcher.watch_directory()
