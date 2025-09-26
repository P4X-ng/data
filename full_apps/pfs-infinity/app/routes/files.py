"""File management routes for listing and downloading user files"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from app.core.browse_conf import get_browse_root, is_traversal_safe, psk_required
from app.core.state import BLUEPRINTS

router = APIRouter()


@router.get("/files")
async def list_files() -> List[Dict[str, Any]]:
    """List all uploaded files (objects)"""
    files = []
    
    # Get objects from BLUEPRINTS (in-memory storage)
    for obj_id, obj_data in BLUEPRINTS.items():
        if isinstance(obj_data, dict) and "sha256" in obj_data:
            files.append({
                "id": obj_id,
                "name": obj_data.get("filename", obj_id.replace("sha256:", "")[:8] + ".bin"),
                "size": obj_data.get("size", 0),
                "sha256": obj_data.get("sha256", ""),
                "compressed_size": int(obj_data.get("size", 0) * 0.05),  # Estimate based on PacketFS compression
                "uploaded_at": obj_data.get("uploaded_at", "")
            })
    
    # Also check browse root for actual files if configured
    browse_root = get_browse_root()
    if browse_root and browse_root.exists():
        uploads_dir = browse_root / "uploads"
        if uploads_dir.exists():
            for file_path in uploads_dir.glob("*"):
                if file_path.is_file():
                    # Check if not already in blueprints
                    file_id = f"file:{file_path.name}"
                    if not any(f["id"] == file_id for f in files):
                        files.append({
                            "id": file_id,
                            "name": file_path.name,
                            "size": file_path.stat().st_size,
                            "sha256": "",
                            "compressed_size": int(file_path.stat().st_size * 0.05),
                            "uploaded_at": ""
                        })
    
    # Sort by name
    files.sort(key=lambda x: x.get("name", ""))
    return files


@router.get("/files/{file_id}/download")
async def download_file(file_id: str):
    """Download a file by its ID"""
    
    # Try to get from BLUEPRINTS first
    if file_id in BLUEPRINTS:
        obj_data = BLUEPRINTS[file_id]
        if "bytes" in obj_data:
            # Return the raw bytes
            data = obj_data["bytes"]
            filename = obj_data.get("filename", f"{file_id.replace(':', '_')}.bin")
            
            def iterate():
                chunk_size = 1 << 20  # 1MB chunks
                for i in range(0, len(data), chunk_size):
                    yield data[i:i + chunk_size]
            
            headers = {
                "Content-Length": str(len(data)),
                "Content-Disposition": f"attachment; filename={filename}"
            }
            return StreamingResponse(iterate(), media_type="application/octet-stream", headers=headers)
    
    # Check if it's a file: reference
    if file_id.startswith("file:"):
        filename = file_id[5:]  # Remove "file:" prefix
        browse_root = get_browse_root()
        if browse_root:
            file_path = browse_root / "uploads" / filename
            if file_path.exists() and is_traversal_safe(browse_root, file_path):
                return FileResponse(
                    path=str(file_path),
                    filename=filename,
                    media_type="application/octet-stream"
                )
    
    raise HTTPException(status_code=404, detail="File not found")


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete a file by its ID"""
    
    # Remove from BLUEPRINTS if exists
    if file_id in BLUEPRINTS:
        del BLUEPRINTS[file_id]
        return {"status": "deleted", "id": file_id}
    
    # Check if it's a file: reference
    if file_id.startswith("file:"):
        filename = file_id[5:]  # Remove "file:" prefix
        browse_root = get_browse_root()
        if browse_root:
            file_path = browse_root / "uploads" / filename
            if file_path.exists() and is_traversal_safe(browse_root, file_path):
                file_path.unlink()
                return {"status": "deleted", "id": file_id}
    
    raise HTTPException(status_code=404, detail="File not found")