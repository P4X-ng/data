"""
WebSocket endpoint for terminal SSH sessions
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import paramiko
import logging
import json
from typing import Optional
import threading
import select

logger = logging.getLogger(__name__)

router = APIRouter()

class SSHSession:
    """Manages an SSH session for a WebSocket connection"""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.ssh_channel: Optional[paramiko.Channel] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.stop_reading = False
        
    async def connect(self, host: str, user: str, port: int = 22, password: Optional[str] = None):
        """Establish SSH connection"""
        try:
            self.ssh_client = paramiko.SSHClient()
            # AutoAddPolicy for demo - in production use proper host key verification
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # First try to get host key fingerprint
            transport = paramiko.Transport((host, port))
            transport.connect()
            key = transport.get_remote_server_key()
            fingerprint = ":".join([format(b, '02x') for b in key.get_fingerprint()])
            transport.close()
            
            # Send host key info to client
            await self.websocket.send_json({
                "type": "host_key",
                "host": host,
                "fingerprint": fingerprint
            })
            
            # Wait for user confirmation (this would come from the client)
            # For now, auto-accept after sending the fingerprint
            await asyncio.sleep(0.1)
            
            # Connect with credentials
            if password:
                self.ssh_client.connect(
                    hostname=host,
                    port=port,
                    username=user,
                    password=password,
                    look_for_keys=False,
                    allow_agent=False,
                    timeout=10
                )
            else:
                # Try with SSH keys
                self.ssh_client.connect(
                    hostname=host,
                    port=port,
                    username=user,
                    timeout=10
                )
            
            # Get an interactive shell
            self.ssh_channel = self.ssh_client.invoke_shell(
                term='xterm-256color',
                width=80,
                height=24
            )
            
            # Start reading thread
            self.start_reader()
            
            # Send success message
            await self.websocket.send_json({
                "type": "connected",
                "message": f"Connected to {user}@{host}"
            })
            
            return True
            
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": str(e)
            })
            return False
    
    def start_reader(self):
        """Start thread to read SSH output"""
        self.stop_reading = False
        self.reader_thread = threading.Thread(target=self._read_ssh_output)
        self.reader_thread.daemon = True
        self.reader_thread.start()
    
    def _read_ssh_output(self):
        """Read output from SSH channel and send to WebSocket"""
        while not self.stop_reading and self.ssh_channel:
            try:
                # Check if data is available
                if self.ssh_channel.recv_ready():
                    data = self.ssh_channel.recv(4096)
                    if data:
                        # Send raw bytes to WebSocket (async, binary frame)
                        asyncio.run(self._send_output_bytes(data))
                else:
                    # Small delay to avoid busy waiting
                    asyncio.run(asyncio.sleep(0.01))
            except Exception as e:
                logger.error(f"Error reading SSH output: {e}")
                break
    
    async def _send_output_bytes(self, data: bytes):
        """Send raw output bytes to WebSocket as a binary frame"""
        try:
            await self.websocket.send_bytes(data)
        except Exception:
            pass
    
    async def send_input(self, data: str):
        """Send input to SSH channel"""
        if self.ssh_channel and not self.ssh_channel.closed:
            self.ssh_channel.send(data)
    
    def resize(self, cols: int, rows: int):
        """Resize terminal"""
        if self.ssh_channel and not self.ssh_channel.closed:
            self.ssh_channel.resize_pty(width=cols, height=rows)
    
    def close(self):
        """Close SSH connection"""
        self.stop_reading = True
        
        if self.ssh_channel:
            self.ssh_channel.close()
            
        if self.ssh_client:
            self.ssh_client.close()
            
        if self.reader_thread:
            self.reader_thread.join(timeout=1)


@router.websocket("/ws/terminal")
async def terminal_websocket(websocket: WebSocket):
    """WebSocket endpoint for terminal SSH sessions"""
    await websocket.accept()
    logger.info("Terminal WebSocket connection established")
    
    session = SSHSession(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "connect":
                    # Connect to SSH
                    host = message.get("host")
                    user = message.get("user", "root")
                    port = message.get("port", 22)
                    password = message.get("password")
                    
                    await session.connect(host, user, port, password)
                    
                elif msg_type == "input":
                    # Send input to SSH
                    input_data = message.get("data", "")
                    await session.send_input(input_data)
                    
                elif msg_type == "resize":
                    # Resize terminal
                    cols = message.get("cols", 80)
                    rows = message.get("rows", 24)
                    session.resize(cols, rows)
                    
                elif msg_type == "disconnect":
                    # Disconnect SSH
                    session.close()
                    break
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except Exception as e:
                logger.error(f"Error handling terminal message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected")
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
    finally:
        session.close()
        try:
            await websocket.close()
        except:
            pass


def register_terminal_routes(app):
    """Register terminal routes with the FastAPI app"""
    app.include_router(router)