from __future__ import annotations

from pydantic import BaseModel
from typing import List, Optional


class BrowseRoot(BaseModel):
    id: str
    type: str  # "virtual" | "fs"
    description: Optional[str] = None
    root: Optional[str] = None


class DirEntry(BaseModel):
    name: str
    is_dir: bool
    size: int
    mtime: float


class FileStat(BaseModel):
    path: str
    relpath: str
    size: int
    mtime: float
    mode: int
    is_dir: bool


class ErrorReply(BaseModel):
    error: str
    detail: Optional[str] = None
