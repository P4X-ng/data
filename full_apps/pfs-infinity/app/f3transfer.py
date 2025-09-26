#!/usr/bin/env /home/punk/.venv/bin/python
"""
F3 Transfer CLI - Lightning Fast File Transfer Utility
Usage: f3transfer [send|receive|relay] [options]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, List
import requests
from tqdm import tqdm
import websocket
import threading

# Configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8811
CHUNK_SIZE = 16 * 1024 * 1024  # 16MB chunks


class F3Transfer:
    """F3 Transfer Client"""
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws/transfer"
        self.ws = None
        
    def send_file(self, file_path: str, target: Optional[str] = None, compress: bool = True) -> bool:
        """
        Send a file to target node or default server
        """
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"Error: File {file_path} not found")
            return False
            
        print(f"\n📤 Sending: {file_path.name}")
        print(f"   Size: {self._format_size(file_path.stat().st_size)}")
        print(f"   Target: {target or self.base_url}")
        
        try:
            # Prepare file for upload
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                
                # Upload with progress bar
                response = self._upload_with_progress(
                    f"{self.base_url}/api/objects",
                    files,
                    file_path.stat().st_size
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"\n✓ Upload complete!")
                    print(f"   ID: {result.get('id')}")
                    print(f"   Compressed: {result.get('compression_ratio', 'N/A')}")
                    print(f"   URL: {result.get('url')}")
                    
                    # If target specified, initiate transfer
                    if target:
                        self._transfer_to_target(result['id'], target)
                    
                    return True
                else:
                    print(f"\n✕ Upload failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"\n✕ Error: {e}")
            return False
    
    def receive_files(self, save_dir: str = "./received") -> None:
        """
        Start receiver mode to accept incoming files
        """
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📥 Receiver started")
        print(f"   Address: {self.host}:{self.port}")
        print(f"   Save to: {save_path.absolute()}")
        print(f"\n   Waiting for incoming files... (Press Ctrl+C to stop)")
        
        try:
            # Start receiver service
            response = requests.post(f"{self.base_url}/api/transfer/receive")
            if response.status_code != 200:
                print(f"✕ Failed to start receiver: {response.text}")
                return
            
            # Connect WebSocket for real-time updates
            self._connect_websocket()
            
            # Keep receiver running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n   Receiver stopped")
        except Exception as e:
            print(f"\n✕ Error: {e}")
    
    def download_file(self, file_id: str, save_path: Optional[str] = None) -> bool:
        """
        Download a file by ID or URL
        """
        print(f"\n📥 Downloading: {file_id}")
        
        try:
            # Request download
            response = requests.post(
                f"{self.base_url}/api/transfer/download",
                json={'url': file_id},
                stream=True
            )
            
            if response.status_code != 200:
                print(f"✕ Download failed: {response.status_code}")
                return False
            
            # Get filename from headers or use default
            filename = response.headers.get('X-Filename', file_id.split('/')[-1] or 'download')
            if save_path:
                file_path = Path(save_path)
            else:
                file_path = Path(filename)
            
            # Download with progress bar
            total_size = int(response.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            print(f"\n✓ Downloaded: {file_path.absolute()}")
            print(f"   Size: {self._format_size(file_path.stat().st_size)}")
            return True
            
        except Exception as e:
            print(f"\n✕ Error: {e}")
            return False
    
    def relay_mode(self, peers: List[str]) -> None:
        """
        Start relay mode to bridge transfers between peers
        """
        print(f"\n🔄 Relay mode started")
        print(f"   Address: {self.host}:{self.port}")
        print(f"   Peers: {', '.join(peers) if peers else 'Auto-discover'}")
        print(f"\n   Relaying transfers... (Press Ctrl+C to stop)")
        
        try:
            # Start relay service
            response = requests.post(f"{self.base_url}/api/transfer/relay")
            if response.status_code != 200:
                print(f"✕ Failed to start relay: {response.text}")
                return
            
            # Keep relay running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n   Relay stopped")
        except Exception as e:
            print(f"\n✕ Error: {e}")
    
    def list_transfers(self) -> None:
        """
        List active and recent transfers
        """
        try:
            response = requests.get(f"{self.base_url}/api/transfer/list")
            if response.status_code == 200:
                data = response.json()
                transfers = data.get('transfers', [])
                
                if not transfers:
                    print("\nNo transfers found")
                    return
                
                print(f"\nRecent Transfers ({data.get('total', 0)} total):")
                print("-" * 60)
                
                for t in transfers[:10]:  # Show last 10
                    status_icon = {
                        'active': '🔄',
                        'complete': '✓',
                        'failed': '✕'
                    }.get(t['status'], '?')
                    
                    print(f"{status_icon} [{t['type']:8}] {t['filename'][:40]}")
                    print(f"   ID: {t['id']}")
                    print(f"   Time: {self._format_time(t['start_time'])}")
                    print()
                    
        except Exception as e:
            print(f"Error listing transfers: {e}")
    
    def get_stats(self) -> None:
        """
        Get transfer statistics
        """
        try:
            response = requests.get(f"{self.base_url}/api/transfer/stats")
            if response.status_code == 200:
                stats = response.json()
                
                print("\n📊 Transfer Statistics")
                print("-" * 40)
                print(f"Total Uploaded:   {self._format_size(stats['total_uploaded'])}")
                print(f"Total Downloaded: {self._format_size(stats['total_downloaded'])}")
                print(f"Compression Rate: {stats['compression_ratio']}")
                print(f"Active Transfers: {stats['active_transfers']}")
                
        except Exception as e:
            print(f"Error getting stats: {e}")
    
    # Helper methods
    
    def _upload_with_progress(self, url: str, files: dict, total_size: int):
        """Upload file with progress bar"""
        from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
        
        # Create multipart encoder
        encoder = MultipartEncoder(fields=files)
        
        # Create progress bar
        pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc="Uploading")
        
        def update_progress(monitor):
            pbar.update(monitor.bytes_read - pbar.n)
        
        # Create monitor
        monitor = MultipartEncoderMonitor(encoder, update_progress)
        
        # Upload
        response = requests.post(
            url,
            data=monitor,
            headers={'Content-Type': monitor.content_type}
        )
        
        pbar.close()
        return response
    
    def _transfer_to_target(self, file_id: str, target: str) -> bool:
        """Initiate transfer to target node"""
        print(f"\n🚀 Transferring to {target}...")
        
        try:
            response = requests.post(
                f"{self.base_url}/transfers",
                json={
                    'object_id': file_id,
                    'receiver_host': target.split(':')[0],
                    'receiver_port': int(target.split(':')[1]) if ':' in target else 8811,
                    'mode': 'websocket'
                }
            )
            
            if response.status_code == 200:
                print("✓ Transfer initiated")
                return True
            else:
                print(f"✕ Transfer failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✕ Transfer error: {e}")
            return False
    
    def _connect_websocket(self):
        """Connect to WebSocket for real-time updates"""
        def on_message(ws, message):
            data = json.loads(message)
            if data.get('type') == 'incoming_file':
                print(f"\n📨 Incoming: {data.get('filename')} from {data.get('sender')}")
            elif data.get('type') == 'progress':
                # Update progress display
                pass
        
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
        
        def on_close(ws):
            print("WebSocket closed")
        
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        # Run WebSocket in background thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
    
    def _format_size(self, bytes: int) -> str:
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} PB"
    
    def _format_time(self, timestamp: float) -> str:
        """Format timestamp to readable time"""
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='F3 Transfer - Lightning Fast File Transfer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  f3transfer send file.txt                     # Send file to default server
  f3transfer send file.txt --target 10.0.0.5   # Send to specific node
  f3transfer receive                           # Start receiver mode
  f3transfer download pfs://abc123             # Download by ID
  f3transfer relay --peers 10.0.0.5,10.0.0.6   # Start relay mode
  f3transfer list                              # List transfers
  f3transfer stats                             # Show statistics
        """
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Send command
    send_parser = subparsers.add_parser('send', help='Send a file')
    send_parser.add_argument('file', help='File to send')
    send_parser.add_argument('--target', help='Target node (host:port)')
    send_parser.add_argument('--no-compress', action='store_true', help='Disable compression')
    
    # Receive command
    receive_parser = subparsers.add_parser('receive', help='Start receiver mode')
    receive_parser.add_argument('--save-dir', default='./received', help='Directory to save files')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download a file')
    download_parser.add_argument('file_id', help='File ID or URL')
    download_parser.add_argument('--save-as', help='Save with custom name')
    
    # Relay command
    relay_parser = subparsers.add_parser('relay', help='Start relay mode')
    relay_parser.add_argument('--peers', help='Comma-separated peer addresses')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List transfers')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    
    # Global options
    parser.add_argument('--host', default=DEFAULT_HOST, help='Server host')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Server port')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Create transfer client
    client = F3Transfer(args.host, args.port)
    
    # Execute command
    if args.command == 'send':
        success = client.send_file(
            args.file,
            args.target,
            compress=not args.no_compress
        )
        sys.exit(0 if success else 1)
        
    elif args.command == 'receive':
        client.receive_files(args.save_dir)
        
    elif args.command == 'download':
        success = client.download_file(args.file_id, args.save_as)
        sys.exit(0 if success else 1)
        
    elif args.command == 'relay':
        peers = args.peers.split(',') if args.peers else []
        client.relay_mode(peers)
        
    elif args.command == 'list':
        client.list_transfers()
        
    elif args.command == 'stats':
        client.get_stats()
        
    else:
        parser.print_help()
        print("\n💡 Try: f3transfer send myfile.txt")


if __name__ == "__main__":
    main()