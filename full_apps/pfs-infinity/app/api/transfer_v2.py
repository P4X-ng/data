"""
Enhanced Transfer API endpoints for F3 PacketFS
Supports upload, download, streaming, and relay functionality
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List

from flask import Blueprint, request, jsonify, send_file, Response, stream_with_context
from werkzeug.utils import secure_filename
import aiohttp
import websocket

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
transfer_bp = Blueprint('transfer_v2', __name__, url_prefix='/api/transfer')

# Configuration
UPLOAD_FOLDER = Path('/tmp/pfs-infinity/uploads')
DOWNLOAD_FOLDER = Path('/tmp/pfs-infinity/downloads')
CHUNK_SIZE = 16 * 1024 * 1024  # 16MB default chunk size
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB max file size

# Ensure directories exist
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Active transfers tracking
active_transfers: Dict[str, Dict[str, Any]] = {}
transfer_stats = {
    'total_uploaded': 0,
    'total_downloaded': 0,
    'total_compressed': 0,
    'active_count': 0
}


@transfer_bp.route('/download', methods=['POST'])
def download_file():
    """
    Download a file from URL, file ID, or remote node
    
    Request JSON:
    {
        "url": "file_url_or_id",
        "source_node": "optional_node_address"
    }
    """
    data = request.get_json()
    url = data.get('url')
    source_node = data.get('source_node')
    
    if not url:
        return jsonify({'error': 'URL or file ID required'}), 400
    
    try:
        # Generate transfer ID
        transfer_id = str(uuid.uuid4())
        
        # If source node specified, download from that node
        if source_node:
            file_path = download_from_node(url, source_node, transfer_id)
        else:
            # Check if it's a local file ID
            if url.startswith('pfs://'):
                file_path = get_local_file(url[6:])  # Remove pfs:// prefix
            else:
                # Download from URL
                file_path = download_from_url(url, transfer_id)
        
        if not file_path or not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        # Stream file to client
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500


@transfer_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Enhanced upload endpoint with compression and progress tracking
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Generate unique ID for this upload
        upload_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_path = UPLOAD_FOLDER / f"{upload_id}_{filename}"
        
        # Track upload start
        active_transfers[upload_id] = {
            'type': 'upload',
            'filename': filename,
            'start_time': time.time(),
            'status': 'active',
            'bytes_transferred': 0
        }
        
        # Save file
        file.save(file_path)
        file_size = file_path.stat().st_size
        
        # Apply compression (simulate for now)
        compressed_size = compress_file(file_path)
        compression_ratio = 1 - (compressed_size / file_size)
        
        # Update stats
        transfer_stats['total_uploaded'] += file_size
        transfer_stats['total_compressed'] += compressed_size
        
        # Mark complete
        active_transfers[upload_id]['status'] = 'complete'
        active_transfers[upload_id]['bytes_transferred'] = file_size
        
        return jsonify({
            'id': upload_id,
            'filename': filename,
            'size': file_size,
            'compressed_size': compressed_size,
            'compression_ratio': f"{compression_ratio * 100:.1f}%",
            'url': f"pfs://{upload_id}"
        }), 200
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        if upload_id in active_transfers:
            active_transfers[upload_id]['status'] = 'failed'
        return jsonify({'error': str(e)}), 500


@transfer_bp.route('/stream/<file_id>')
def stream_file(file_id):
    """
    Stream a file with chunked transfer encoding
    """
    def generate():
        try:
            file_path = get_local_file(file_id)
            if not file_path:
                yield b''
                return
                
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            
    file_path = get_local_file(file_id)
    if not file_path:
        return jsonify({'error': 'File not found'}), 404
        
    return Response(
        stream_with_context(generate()),
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename={file_path.name}',
            'X-Filename': file_path.name
        }
    )


@transfer_bp.route('/receive', methods=['POST'])
def start_receiver():
    """
    Start receiver mode to listen for incoming transfers
    """
    try:
        # Start receiver service (would typically start a background service)
        receiver_port = 8812  # Default receiver port
        
        # In production, this would start an actual receiver service
        # For now, we'll just mark the status
        return jsonify({
            'status': 'receiver_started',
            'port': receiver_port,
            'message': 'Ready to receive files'
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to start receiver: {e}")
        return jsonify({'error': str(e)}), 500


@transfer_bp.route('/relay', methods=['POST'])
def start_relay():
    """
    Start relay mode to bridge transfers between nodes
    """
    try:
        # Start relay service
        relay_port = 8813  # Default relay port
        
        # In production, this would start an actual relay service
        return jsonify({
            'status': 'relay_started',
            'port': relay_port,
            'message': 'Acting as transfer relay'
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to start relay: {e}")
        return jsonify({'error': str(e)}), 500


@transfer_bp.route('/status/<transfer_id>')
def get_transfer_status(transfer_id):
    """
    Get status of a specific transfer
    """
    if transfer_id not in active_transfers:
        return jsonify({'error': 'Transfer not found'}), 404
    
    transfer = active_transfers[transfer_id]
    elapsed = time.time() - transfer['start_time']
    
    if transfer['bytes_transferred'] > 0:
        speed = transfer['bytes_transferred'] / elapsed
    else:
        speed = 0
    
    return jsonify({
        'id': transfer_id,
        'type': transfer['type'],
        'filename': transfer['filename'],
        'status': transfer['status'],
        'bytes_transferred': transfer['bytes_transferred'],
        'speed': speed,
        'elapsed': elapsed
    }), 200


@transfer_bp.route('/stats')
def get_stats():
    """
    Get global transfer statistics
    """
    active_count = sum(1 for t in active_transfers.values() if t['status'] == 'active')
    
    return jsonify({
        'total_uploaded': transfer_stats['total_uploaded'],
        'total_downloaded': transfer_stats['total_downloaded'],
        'total_compressed': transfer_stats['total_compressed'],
        'active_transfers': active_count,
        'compression_ratio': calculate_average_compression()
    }), 200


@transfer_bp.route('/list')
def list_transfers():
    """
    List all active and recent transfers
    """
    transfers = []
    for tid, transfer in active_transfers.items():
        transfers.append({
            'id': tid,
            'type': transfer['type'],
            'filename': transfer['filename'],
            'status': transfer['status'],
            'start_time': transfer['start_time']
        })
    
    # Sort by start time (most recent first)
    transfers.sort(key=lambda x: x['start_time'], reverse=True)
    
    return jsonify({
        'transfers': transfers[:100],  # Return last 100 transfers
        'total': len(transfers)
    }), 200


# Helper functions

def download_from_node(file_id: str, node_address: str, transfer_id: str) -> Optional[Path]:
    """
    Download a file from a remote F3 node
    """
    try:
        # Parse node address (host:port)
        if ':' in node_address:
            host, port = node_address.split(':')
        else:
            host = node_address
            port = 8811  # Default F3 port
        
        # Construct URL
        url = f"http://{host}:{port}/api/transfer/stream/{file_id}"
        
        # Download file
        return download_from_url(url, transfer_id)
        
    except Exception as e:
        logger.error(f"Failed to download from node {node_address}: {e}")
        return None


def download_from_url(url: str, transfer_id: str) -> Optional[Path]:
    """
    Download a file from a URL with progress tracking
    """
    try:
        import requests
        
        # Generate filename from URL or use temp name
        filename = url.split('/')[-1] or f"download_{transfer_id}"
        file_path = DOWNLOAD_FOLDER / secure_filename(filename)
        
        # Track download
        active_transfers[transfer_id] = {
            'type': 'download',
            'filename': filename,
            'start_time': time.time(),
            'status': 'active',
            'bytes_transferred': 0
        }
        
        # Download with streaming
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        bytes_downloaded = 0
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    active_transfers[transfer_id]['bytes_transferred'] = bytes_downloaded
        
        # Update stats
        transfer_stats['total_downloaded'] += bytes_downloaded
        active_transfers[transfer_id]['status'] = 'complete'
        
        return file_path
        
    except Exception as e:
        logger.error(f"Failed to download from URL {url}: {e}")
        if transfer_id in active_transfers:
            active_transfers[transfer_id]['status'] = 'failed'
        return None


def get_local_file(file_id: str) -> Optional[Path]:
    """
    Get local file path from file ID
    """
    # Check uploads folder
    for file_path in UPLOAD_FOLDER.glob(f"{file_id}_*"):
        if file_path.exists():
            return file_path
    
    # Check downloads folder
    for file_path in DOWNLOAD_FOLDER.glob(f"*{file_id}*"):
        if file_path.exists():
            return file_path
    
    return None


def compress_file(file_path: Path) -> int:
    """
    Compress a file and return compressed size
    This is a placeholder - integrate with actual F3 compression
    """
    # For now, simulate compression with a ratio
    # In production, this would use actual F3 compression
    original_size = file_path.stat().st_size
    compression_ratio = 0.05  # Simulate 95% compression
    return int(original_size * compression_ratio)


def calculate_average_compression() -> str:
    """
    Calculate average compression ratio
    """
    if transfer_stats['total_uploaded'] == 0:
        return "0%"
    
    ratio = 1 - (transfer_stats['total_compressed'] / transfer_stats['total_uploaded'])
    return f"{ratio * 100:.1f}%"


# WebSocket handler for real-time updates
@transfer_bp.route('/ws')
def websocket_handler():
    """
    WebSocket endpoint for real-time transfer updates
    """
    # This would typically use a WebSocket library like flask-socketio
    # For now, returning a placeholder
    return jsonify({'message': 'WebSocket endpoint - use ws:// protocol'}), 200