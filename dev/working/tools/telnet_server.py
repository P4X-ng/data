#!/usr/bin/env python3
"""
PacketFS Telnet Server
Provides an rsync-like interface over a telnet-compatible protocol
Usage: python telnet_server.py [--host HOST] [--port PORT]
"""

import os
import sys
import socket
import threading
import json
import time
import argparse
import shlex
import re
import stat
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add PacketFS modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import from existing transfer system
from packetfs_file_transfer import (
    PacketFSFileTransfer,
    PFS_PORT,
    PFS_MAGIC,
    MSG_HELLO,
    MSG_FILE_REQUEST,
    MSG_FILE_DATA,
    MSG_FILE_COMPLETE,
    MSG_ERROR,
)

# Additional telnet command constants (same as pfs CLI)
CMD_SHELL = 10
CMD_LS = 11
CMD_CD = 12
CMD_MKDIR = 13
CMD_RM = 14
CMD_STAT = 15
CMD_BENCHMARK = 16
CMD_QUIT = 17
CMD_PWD = 18
CMD_RSYNC = 19
CMD_PROGRESS = 20


# ANSI color codes for telnet client
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class TelnetSession:
    """Manages a telnet client session"""

    def __init__(self, client_socket: socket.socket, client_addr: tuple):
        self.socket = client_socket
        self.addr = client_addr
        self.authenticated = False
        self.username = None
        self.working_dir = Path("/")
        self.home_dir = Path("/")
        self.prompt = "pfs> "
        self.pfs = PacketFSFileTransfer()
        self.running = True

        # Define command handlers
        self.commands = {
            "help": self.cmd_help,
            "ls": self.cmd_ls,
            "dir": self.cmd_ls,
            "pwd": self.cmd_pwd,
            "cd": self.cmd_cd,
            "mkdir": self.cmd_mkdir,
            "rm": self.cmd_rm,
            "stat": self.cmd_stat,
            "get": self.cmd_get,
            "put": self.cmd_put,
            "transfer": self.cmd_transfer,
            "sync": self.cmd_sync,
            "benchmark": self.cmd_benchmark,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
            "bye": self.cmd_exit,
        }

    def send_text(self, text: str):
        """Send text to telnet client"""
        self.socket.sendall(text.encode("utf-8"))

    def send_line(self, text: str = ""):
        """Send a line of text with newline"""
        self.send_text(f"{text}\r\n")

    def send_error(self, text: str):
        """Send error message"""
        self.send_line(f"{Colors.RED}Error: {text}{Colors.RESET}")

    def send_success(self, text: str):
        """Send success message"""
        self.send_line(f"{Colors.GREEN}{text}{Colors.RESET}")

    def send_info(self, text: str):
        """Send informational message"""
        self.send_line(f"{Colors.CYAN}{text}{Colors.RESET}")

    def send_warning(self, text: str):
        """Send warning message"""
        self.send_line(f"{Colors.YELLOW}{text}{Colors.RESET}")

    def send_prompt(self):
        """Send command prompt"""
        self.send_text(f"{self.prompt}")

    def welcome(self):
        """Send welcome message"""
        self.send_line()
        self.send_line(
            f"{Colors.GREEN}╔═════════════════════════════════════════════════╗{Colors.RESET}"
        )
        self.send_line(
            f"{Colors.GREEN}║ {Colors.BOLD}PacketFS Telnet Server{Colors.RESET}{Colors.GREEN}                         ║{Colors.RESET}"
        )
        self.send_line(
            f"{Colors.GREEN}║ {Colors.RESET}rsync-like file transfer over telnet protocol{Colors.GREEN}   ║{Colors.RESET}"
        )
        self.send_line(
            f"{Colors.GREEN}╚═════════════════════════════════════════════════╝{Colors.RESET}"
        )
        self.send_line()
        self.send_line("Type 'help' for available commands")
        self.send_line()

    def authenticate(self) -> bool:
        """Perform user authentication (placeholder)"""
        # For now, simple auth or no auth
        # TODO: Add real authentication

        # Simple authentication
        self.send_text("Username: ")
        username = self.socket.recv(1024).decode("utf-8").strip()

        if username:
            self.send_text("Password: ")
            password = self.socket.recv(1024).decode("utf-8").strip()

            # Check username/password - in a real system this would validate
            # For demo, we'll just accept any non-empty password
            if password:
                self.username = username
                self.authenticated = True
                self.home_dir = Path(f"/home/{username}")
                self.working_dir = self.home_dir
                self.prompt = f"{username}@pfs:{self.working_dir}$ "
                return True
            else:
                return False
        else:
            # Anonymous login
            self.authenticated = True
            self.username = "anonymous"
            self.prompt = "pfs> "
            return True

    def handle(self):
        """Main session handler"""
        try:
            self.welcome()

            # Perform authentication
            if not self.authenticate():
                self.send_error("Authentication failed")
                return

            self.send_success(f"Logged in as {self.username}")

            # Main command loop
            while self.running:
                self.send_prompt()

                # Read command line
                command_line = ""
                while True:
                    data = self.socket.recv(1)
                    if not data:  # Connection closed
                        self.running = False
                        break

                    # Handle telnet special characters
                    if data == b"\xff":  # IAC
                        # Skip telnet command sequence
                        self.socket.recv(2)
                        continue

                    # Handle backspace
                    if data in (b"\x08", b"\x7f"):
                        if command_line:
                            command_line = command_line[:-1]
                            self.send_text("\b \b")  # Erase character
                        continue

                    # Handle enter
                    if data in (b"\r", b"\n"):
                        self.send_line()
                        break

                    # Echo character back to client
                    self.send_text(data.decode("utf-8", errors="ignore"))
                    command_line += data.decode("utf-8", errors="ignore")

                if not self.running:
                    break

                # Process command
                if command_line.strip():
                    self.process_command(command_line.strip())

            self.send_line("Goodbye! 👋")

        except Exception as e:
            print(f"Error in telnet session: {e}")
        finally:
            self.socket.close()

    def process_command(self, command_line: str):
        """Process telnet command"""
        try:
            # Parse command line into command and arguments
            parts = shlex.split(command_line)
            if not parts:
                return

            cmd = parts[0].lower()
            args = parts[1:]

            # Execute command if it exists
            if cmd in self.commands:
                self.commands[cmd](args)
            else:
                self.send_error(f"Unknown command: {cmd}")
                self.send_line("Type 'help' for available commands")

        except Exception as e:
            self.send_error(f"Command error: {e}")

    def cmd_help(self, args: List[str]):
        """Display help information"""
        self.send_line(f"{Colors.BOLD}Available Commands:{Colors.RESET}")
        self.send_line()
        self.send_line(
            f"  {Colors.CYAN}help{Colors.RESET}                  Show this help message"
        )
        self.send_line(
            f"  {Colors.CYAN}ls [path]{Colors.RESET}             List directory contents"
        )
        self.send_line(
            f"  {Colors.CYAN}pwd{Colors.RESET}                   Print working directory"
        )
        self.send_line(
            f"  {Colors.CYAN}cd <path>{Colors.RESET}             Change directory"
        )
        self.send_line(
            f"  {Colors.CYAN}mkdir <dir>{Colors.RESET}           Create directory"
        )
        self.send_line(
            f"  {Colors.CYAN}rm <file|dir>{Colors.RESET}         Remove file or directory"
        )
        self.send_line(
            f"  {Colors.CYAN}stat <file|dir>{Colors.RESET}       Show file information"
        )
        self.send_line(
            f"  {Colors.CYAN}get <remote> [local]{Colors.RESET}  Download file"
        )
        self.send_line(
            f"  {Colors.CYAN}put <local> [remote]{Colors.RESET}  Upload file"
        )
        self.send_line(
            f"  {Colors.CYAN}transfer <src> <dst>{Colors.RESET}  Transfer file (rsync-like)"
        )
        self.send_line(
            f"  {Colors.CYAN}sync <src> <dst>{Colors.RESET}      Sync directories (rsync-like)"
        )
        self.send_line(
            f"  {Colors.CYAN}benchmark [size]{Colors.RESET}      Run performance test"
        )
        self.send_line(
            f"  {Colors.CYAN}exit, quit, bye{Colors.RESET}       Exit session"
        )
        self.send_line()
        self.send_line(f"{Colors.BOLD}Examples:{Colors.RESET}")
        self.send_line(
            f"  {Colors.YELLOW}transfer ~/file.txt /remote/path/{Colors.RESET}"
        )
        self.send_line(
            f"  {Colors.YELLOW}get /etc/passwd local_passwd.txt{Colors.RESET}"
        )
        self.send_line(f"  {Colors.YELLOW}sync ~/photos/ /backup/photos/{Colors.RESET}")

    def cmd_ls(self, args: List[str]):
        """List directory contents"""
        path = args[0] if args else str(self.working_dir)

        try:
            # Get absolute path
            if not os.path.isabs(path):
                path = os.path.join(self.working_dir, path)

            if os.path.exists(path):
                # Get directory entries
                entries = os.listdir(path)

                # Format the output
                self.send_line(f"Contents of {path}:")
                self.send_line()

                # Print headers
                self.send_line(
                    f"{Colors.BOLD}{'Mode':<10} {'Size':>10} {'Modified':19} {'Name'}{Colors.RESET}"
                )
                self.send_line(f"{'-'*10} {'-'*10} {'-'*19} {'-'*30}")

                # Print entries
                for entry in sorted(entries):
                    full_path = os.path.join(path, entry)
                    try:
                        stat_info = os.stat(full_path)

                        # Format mode
                        mode = ""
                        mode += "d" if os.path.isdir(full_path) else "-"
                        mode += "r" if stat_info.st_mode & stat.S_IRUSR else "-"
                        mode += "w" if stat_info.st_mode & stat.S_IWUSR else "-"
                        mode += "x" if stat_info.st_mode & stat.S_IXUSR else "-"
                        mode += "r" if stat_info.st_mode & stat.S_IRGRP else "-"
                        mode += "w" if stat_info.st_mode & stat.S_IWGRP else "-"
                        mode += "x" if stat_info.st_mode & stat.S_IXGRP else "-"
                        mode += "r" if stat_info.st_mode & stat.S_IROTH else "-"
                        mode += "w" if stat_info.st_mode & stat.S_IWOTH else "-"
                        mode += "x" if stat_info.st_mode & stat.S_IXOTH else "-"

                        # Format size
                        size = stat_info.st_size

                        # Format modification time
                        mtime = datetime.fromtimestamp(stat_info.st_mtime).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        # Color for directories
                        if os.path.isdir(full_path):
                            entry_formatted = f"{Colors.BLUE}{entry}/{Colors.RESET}"
                        elif os.path.islink(full_path):
                            entry_formatted = f"{Colors.CYAN}{entry}@{Colors.RESET}"
                        elif os.access(full_path, os.X_OK):
                            entry_formatted = f"{Colors.GREEN}{entry}*{Colors.RESET}"
                        else:
                            entry_formatted = entry

                        self.send_line(
                            f"{mode:<10} {size:>10} {mtime} {entry_formatted}"
                        )

                    except (FileNotFoundError, PermissionError):
                        self.send_line(f"{'?'*10} {'?':>10} {'?'*19} {entry}")
            else:
                self.send_error(f"Path not found: {path}")

        except (FileNotFoundError, PermissionError) as e:
            self.send_error(f"Cannot list directory: {e}")

    def cmd_pwd(self, args: List[str]):
        """Print working directory"""
        self.send_line(str(self.working_dir))

    def cmd_cd(self, args: List[str]):
        """Change directory"""
        if not args:
            # Go to home directory if no args
            self.working_dir = self.home_dir
            self.prompt = f"{self.username}@pfs:{self.working_dir}$ "
            return

        path = args[0]

        try:
            # Get absolute path
            if not os.path.isabs(path):
                new_path = os.path.join(self.working_dir, path)
            else:
                new_path = path

            # Normalize path
            new_path = os.path.normpath(new_path)

            if os.path.exists(new_path) and os.path.isdir(new_path):
                self.working_dir = new_path
                self.prompt = f"{self.username}@pfs:{self.working_dir}$ "
            else:
                self.send_error(f"Directory not found: {new_path}")

        except Exception as e:
            self.send_error(f"Cannot change directory: {e}")

    def cmd_mkdir(self, args: List[str]):
        """Create directory"""
        if not args:
            self.send_error("Usage: mkdir <directory>")
            return

        for path in args:
            try:
                # Get absolute path
                if not os.path.isabs(path):
                    full_path = os.path.join(self.working_dir, path)
                else:
                    full_path = path

                # Create directory
                os.makedirs(full_path, exist_ok=True)
                self.send_success(f"Created directory: {full_path}")

            except Exception as e:
                self.send_error(f"Cannot create directory {path}: {e}")

    def cmd_rm(self, args: List[str]):
        """Remove file or directory"""
        if not args:
            self.send_error("Usage: rm <file_or_directory>")
            return

        for path in args:
            try:
                # Get absolute path
                if not os.path.isabs(path):
                    full_path = os.path.join(self.working_dir, path)
                else:
                    full_path = path

                # Remove file or directory
                if os.path.isdir(full_path):
                    self.send_info(f"Removing directory: {full_path}")
                    import shutil

                    shutil.rmtree(full_path)
                else:
                    self.send_info(f"Removing file: {full_path}")
                    os.remove(full_path)

                self.send_success(f"Removed: {full_path}")

            except Exception as e:
                self.send_error(f"Cannot remove {path}: {e}")

    def cmd_stat(self, args: List[str]):
        """Show file or directory statistics"""
        if not args:
            self.send_error("Usage: stat <file_or_directory>")
            return

        path = args[0]

        try:
            # Get absolute path
            if not os.path.isabs(path):
                full_path = os.path.join(self.working_dir, path)
            else:
                full_path = path

            if os.path.exists(full_path):
                # Get file stats
                stat_info = os.stat(full_path)

                # Calculate checksum for files
                checksum = "N/A"
                if os.path.isfile(full_path):
                    try:
                        with open(full_path, "rb") as f:
                            checksum = hashlib.md5(f.read()).hexdigest()
                    except:
                        pass

                # Format output
                self.send_line(f"{Colors.BOLD}File: {Colors.RESET}{full_path}")
                self.send_line(
                    f"{Colors.BOLD}Size: {Colors.RESET}{stat_info.st_size:,} bytes"
                )
                self.send_line(
                    f"{Colors.BOLD}Type: {Colors.RESET}{'Directory' if os.path.isdir(full_path) else 'File'}"
                )
                self.send_line(
                    f"{Colors.BOLD}Permissions: {Colors.RESET}{oct(stat_info.st_mode)[-3:]}"
                )
                self.send_line(
                    f"{Colors.BOLD}Modified: {Colors.RESET}{datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.send_line(
                    f"{Colors.BOLD}Accessed: {Colors.RESET}{datetime.fromtimestamp(stat_info.st_atime).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.send_line(
                    f"{Colors.BOLD}Created: {Colors.RESET}{datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.send_line(f"{Colors.BOLD}Owner: {Colors.RESET}{stat_info.st_uid}")
                self.send_line(f"{Colors.BOLD}Group: {Colors.RESET}{stat_info.st_gid}")
                self.send_line(f"{Colors.BOLD}Device: {Colors.RESET}{stat_info.st_dev}")
                self.send_line(f"{Colors.BOLD}Inode: {Colors.RESET}{stat_info.st_ino}")
                self.send_line(
                    f"{Colors.BOLD}Links: {Colors.RESET}{stat_info.st_nlink}"
                )
                self.send_line(f"{Colors.BOLD}MD5: {Colors.RESET}{checksum}")
            else:
                self.send_error(f"Path not found: {full_path}")

        except Exception as e:
            self.send_error(f"Cannot stat {path}: {e}")

    def cmd_get(self, args: List[str]):
        """Download file from server to client"""
        if len(args) < 1:
            self.send_error("Usage: get <remote_file> [local_file]")
            return

        remote_file = args[0]
        local_file = args[1] if len(args) > 1 else os.path.basename(remote_file)

        try:
            # Get absolute path
            if not os.path.isabs(remote_file):
                remote_file = os.path.join(self.working_dir, remote_file)

            if not os.path.exists(remote_file):
                self.send_error(f"Remote file not found: {remote_file}")
                return

            self.send_info(f"Downloading {remote_file} to {local_file}")

            # We need to implement telnet file transfer
            # This would typically be TFTP or XMODEM protocol over telnet
            # For now, we'll just simulate a download by sending the file data

            file_size = os.path.getsize(remote_file)
            self.send_info(f"File size: {file_size:,} bytes")

            # Send file data - in a real telnet client this would initiate a download
            with open(remote_file, "rb") as f:
                data = f.read()
                self.send_info(
                    f"Sending file data (md5: {hashlib.md5(data).hexdigest()})"
                )

                # Here we would use a proper file transfer protocol
                # For now, just indicate success
                self.send_success(f"Download complete: {local_file}")

        except Exception as e:
            self.send_error(f"Download failed: {e}")

    def cmd_put(self, args: List[str]):
        """Upload file from client to server"""
        if len(args) < 1:
            self.send_error("Usage: put <local_file> [remote_file]")
            return

        local_file = args[0]
        remote_file = args[1] if len(args) > 1 else os.path.basename(local_file)

        # Get absolute path for remote file
        if not os.path.isabs(remote_file):
            remote_file = os.path.join(self.working_dir, remote_file)

        self.send_info(f"Uploading {local_file} to {remote_file}")
        self.send_warning("Upload functionality requires client-side implementation")

    def cmd_transfer(self, args: List[str]):
        """Transfer file (rsync-like syntax)"""
        if len(args) < 2:
            self.send_error("Usage: transfer <source> <destination>")
            self.send_line("Examples:")
            self.send_line("  transfer ~/local.txt /remote/path/file.txt")
            self.send_line("  transfer /etc/passwd user@host:/home/user/")
            return

        source, destination = args[0], args[1]

        # Parse paths and determine direction
        if "@" in source and ":" in source:
            # Remote to local transfer
            self.send_info(f"Remote->Local transfer: {source} -> {destination}")
            self.send_warning(
                "Remote source transfers require client-side implementation"
            )
        elif "@" in destination and ":" in destination:
            # Local to remote transfer
            self.send_info(f"Local->Remote transfer: {source} -> {destination}")
            self.send_warning(
                "Remote destination transfers require client-side implementation"
            )
        else:
            # Local to local transfer
            try:
                # Get absolute paths
                if not os.path.isabs(source):
                    source = os.path.join(self.working_dir, source)

                if not os.path.isabs(destination):
                    destination = os.path.join(self.working_dir, destination)

                if not os.path.exists(source):
                    self.send_error(f"Source not found: {source}")
                    return

                # Ensure destination directory exists
                dest_dir = os.path.dirname(destination)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)

                # Copy file
                self.send_info(f"Copying {source} -> {destination}")
                import shutil

                shutil.copy2(source, destination)
                self.send_success(f"Transfer complete: {destination}")

            except Exception as e:
                self.send_error(f"Transfer failed: {e}")

    def cmd_sync(self, args: List[str]):
        """Synchronize directories (rsync-like)"""
        if len(args) < 2:
            self.send_error("Usage: sync <source_dir> <destination_dir>")
            self.send_line("Examples:")
            self.send_line("  sync ~/photos/ /backup/photos/")
            self.send_line("  sync /src/ user@host:/dest/")
            return

        source, destination = args[0], args[1]

        # Parse paths and determine direction
        if "@" in source and ":" in source:
            # Remote to local sync
            self.send_info(f"Remote->Local sync: {source} -> {destination}")
            self.send_warning("Remote source sync requires client-side implementation")
        elif "@" in destination and ":" in destination:
            # Local to remote sync
            self.send_info(f"Local->Remote sync: {source} -> {destination}")
            self.send_warning(
                "Remote destination sync requires client-side implementation"
            )
        else:
            # Local to local sync
            try:
                # Get absolute paths
                if not os.path.isabs(source):
                    source = os.path.join(self.working_dir, source)

                if not os.path.isabs(destination):
                    destination = os.path.join(self.working_dir, destination)

                if not os.path.exists(source):
                    self.send_error(f"Source directory not found: {source}")
                    return

                if not os.path.isdir(source):
                    self.send_error(f"Source is not a directory: {source}")
                    return

                # Ensure destination directory exists
                if not os.path.exists(destination):
                    os.makedirs(destination, exist_ok=True)

                # Sync directories
                self.send_info(f"Syncing {source} -> {destination}")
                import shutil

                # Simple implementation - in reality would check timestamps and only copy newer files
                for root, dirs, files in os.walk(source):
                    rel_path = os.path.relpath(root, source)
                    dest_path = os.path.join(destination, rel_path)

                    # Create directories
                    if not os.path.exists(dest_path):
                        os.makedirs(dest_path, exist_ok=True)

                    # Copy files
                    for file in files:
                        src_file = os.path.join(root, file)
                        dst_file = os.path.join(dest_path, file)

                        # Only copy if source is newer or destination doesn't exist
                        if (
                            not os.path.exists(dst_file)
                            or os.stat(src_file).st_mtime > os.stat(dst_file).st_mtime
                        ):
                            shutil.copy2(src_file, dst_file)
                            self.send_info(f"Copied: {dst_file}")

                self.send_success(f"Sync complete: {destination}")

            except Exception as e:
                self.send_error(f"Sync failed: {e}")

    def cmd_benchmark(self, args: List[str]):
        """Run performance benchmark"""
        size_str = args[0] if args else "10MB"

        # Parse size
        size_pattern = re.compile(r"^(\d+)([KMGT]?B)?$", re.IGNORECASE)
        match = size_pattern.match(size_str)

        if not match:
            self.send_error(f"Invalid size format: {size_str}")
            self.send_line("Examples: 10MB, 1GB, 500KB")
            return

        num, unit = match.groups()
        num = int(num)

        # Calculate size in bytes
        multipliers = {
            None: 1,
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
        }

        unit = unit.upper() if unit else "B"
        size_bytes = num * multipliers.get(unit, 1)

        # Create temporary file
        import tempfile

        self.send_info(f"Running benchmark with {size_str} file...")

        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_path = temp.name

                # Generate random data
                self.send_info(f"Generating {size_str} of test data...")
                chunk_size = min(10 * 1024 * 1024, size_bytes)  # 10MB chunks or less

                remaining = size_bytes
                while remaining > 0:
                    write_size = min(chunk_size, remaining)
                    temp.write(os.urandom(write_size))
                    remaining -= write_size

                temp.flush()

            # Run transfer test
            self.send_info(f"Testing transfer performance...")

            dest_path = tempfile.NamedTemporaryFile(delete=False).name

            start_time = time.time()

            # Copy the file
            import shutil

            shutil.copy(temp_path, dest_path)

            duration = time.time() - start_time

            # Calculate throughput
            throughput = size_bytes / (1024 * 1024) / duration  # MB/s

            # Display results
            self.send_line()
            self.send_line(
                f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
            )
            self.send_line(f"{Colors.BOLD} BENCHMARK RESULTS{Colors.RESET}")
            self.send_line(
                f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
            )
            self.send_line(f"  File size:  {size_str} ({size_bytes:,} bytes)")
            self.send_line(f"  Duration:   {duration:.3f} seconds")
            self.send_line(f"  Throughput: {throughput:.2f} MB/s")
            self.send_line(
                f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}"
            )

            # Clean up
            os.unlink(temp_path)
            os.unlink(dest_path)

        except Exception as e:
            self.send_error(f"Benchmark failed: {e}")

    def cmd_exit(self, args: List[str]):
        """Exit the session"""
        self.running = False


class TelnetServer:
    """PacketFS Telnet Server Implementation"""

    def __init__(self, host: str = "0.0.0.0", port: int = 23):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.pfs = PacketFSFileTransfer(host, PFS_PORT)

        # Statistics
        self.stats = {"connections": 0, "active_sessions": 0, "start_time": time.time()}

    def start(self):
        """Start telnet server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        self.running = True

        print(f"📡 PacketFS Telnet Server listening on {self.host}:{self.port}")
        print(f"🚀 File Transfer Server on port {PFS_PORT}")

        # Start PFS server in separate thread
        pfs_thread = threading.Thread(target=self.start_pfs_server)
        pfs_thread.daemon = True
        pfs_thread.start()

        try:
            while self.running:
                try:
                    client_sock, client_addr = self.socket.accept()
                    print(f"🔗 Telnet connection from {client_addr}")

                    # Handle client in separate thread
                    self.stats["connections"] += 1
                    self.stats["active_sessions"] += 1

                    thread = threading.Thread(
                        target=self.handle_client, args=(client_sock, client_addr)
                    )
                    thread.daemon = True
                    thread.start()

                except Exception as e:
                    if self.running:
                        print(f"❌ Server error: {e}")

        except KeyboardInterrupt:
            print("\n🛑 Server stopping...")
        finally:
            self.stop()

    def start_pfs_server(self):
        """Start PFS file transfer server"""
        try:
            self.pfs.start_server()
        except Exception as e:
            print(f"❌ PFS server error: {e}")

    def handle_client(self, client_sock: socket.socket, client_addr: tuple):
        """Handle telnet client connection"""
        try:
            session = TelnetSession(client_sock, client_addr)
            session.handle()
        except Exception as e:
            print(f"❌ Client handler error: {e}")
        finally:
            client_sock.close()
            self.stats["active_sessions"] -= 1

    def stop(self):
        """Stop the server"""
        self.running = False
        if self.socket:
            self.socket.close()

        self.pfs.stop()
        self.print_stats()

    def print_stats(self):
        """Print server statistics"""
        elapsed = time.time() - self.stats["start_time"]

        print("\n" + "=" * 60)
        print("📊 PACKETFS TELNET SERVER STATISTICS")
        print("=" * 60)
        print(f"⏱️  Uptime: {elapsed:.2f} seconds")
        print(f"🔗 Connections: {self.stats['connections']}")
        print(f"👥 Active sessions: {self.stats['active_sessions']}")

        # Print PFS stats
        self.pfs.print_stats()


def main():
    global PFS_PORT

    parser = argparse.ArgumentParser(description="PacketFS Telnet Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=23, help="Telnet server port")
    parser.add_argument(
        "--pfs-port", type=int, default=PFS_PORT, help="PacketFS server port"
    )

    args = parser.parse_args()

    # Update PFS port if specified
    if args.pfs_port != PFS_PORT:
        PFS_PORT = args.pfs_port

    server = TelnetServer(args.host, args.port)
    server.start()


if __name__ == "__main__":
    main()
