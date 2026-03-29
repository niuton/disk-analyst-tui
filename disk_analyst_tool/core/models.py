from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class FileInfo(BaseModel):
    path: Path
    size: int  # bytes
    modified: datetime


class DiskTree(BaseModel):
    name: str
    path: Path
    size: int  # bytes (aggregate for directories)
    children: list[DiskTree] = []


class DiskUsage(BaseModel):
    total: int
    used: int
    free: int
    percent: float


class CleanTarget(BaseModel):
    path: Path
    category: str  # e.g. "ds_store", "pycache", "node_modules", "cache"
    size: int
    safe: bool  # True = auto-clean, False = needs confirmation


class CleanResult(BaseModel):
    cleaned: int  # number of targets cleaned
    bytes_freed: int
    errors: list[str] = []


class Package(BaseModel):
    name: str
    version: str
    size: int  # bytes, 0 if unknown
    manager: str  # "homebrew", "npm", "pip"
    is_orphan: bool = False
