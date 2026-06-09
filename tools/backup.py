"""Backup snapshot MCP tools."""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "logs", ".backups"}


def _resolve_dir(path: str, access: str) -> Path:
    target = resolve_allowed_path(path, access=access)
    if target.exists() and not target.is_dir():
        raise PolicyError("path_not_directory", "path must be a directory", {"path": str(target)})
    return target


def _iter_snapshot_files(root: Path, max_files: int, max_file_size: int):
    files = []
    for current_root, dirs, names in os.walk(root):
        current = Path(current_root)
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        for name in names:
            path = current / name
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue
            files.append(path)
            if len(files) >= max_files:
                return files
    return files


def register(mcp) -> None:
    """Register backup tools."""

    @mcp.tool()
    def plan_backup_snapshot(source_path: str, max_files: int = 500, max_file_size: int = 2_000_000) -> dict:
        """Plan a backup snapshot without writing it."""
        try:
            source = _resolve_dir(source_path, "read")
            files = _iter_snapshot_files(source, max(1, min(int(max_files), 5000)), max(1_000, min(int(max_file_size), 20_000_000)))
        except PolicyError as exc:
            audit("backup.plan_backup_snapshot", False, {"source_path": source_path, "error": exc.code})
            return policy_error_result(exc)
        total_bytes = sum(path.stat().st_size for path in files)
        return {"success": True, "source_path": str(source), "file_count": len(files), "total_bytes": total_bytes, "sample_files": [str(path.relative_to(source)) for path in files[:50]]}

    @mcp.tool()
    def create_backup_snapshot(source_path: str, destination_dir: str | None = None, max_files: int = 500, max_file_size: int = 2_000_000) -> dict:
        """Create a zip snapshot in an allowed destination directory."""
        try:
            source = _resolve_dir(source_path, "read")
            destination = _resolve_dir(destination_dir or str(source / ".backups"), "write")
            destination.mkdir(parents=True, exist_ok=True)
            files = _iter_snapshot_files(source, max(1, min(int(max_files), 5000)), max(1_000, min(int(max_file_size), 20_000_000)))
            archive = destination / f"{source.name}-snapshot-{int(time.time())}.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
                for path in files:
                    if archive in path.parents or path == archive:
                        continue
                    handle.write(path, path.relative_to(source))
        except PolicyError as exc:
            audit("backup.create_backup_snapshot", False, {"source_path": source_path, "error": exc.code})
            return policy_error_result(exc)
        audit("backup.create_backup_snapshot", True, {"source_path": str(source), "archive": str(archive), "file_count": len(files)})
        return {"success": True, "source_path": str(source), "archive_path": str(archive), "file_count": len(files), "size_bytes": archive.stat().st_size}

    @mcp.tool()
    def list_backup_snapshots(destination_dir: str) -> dict:
        """List backup snapshot zip files."""
        try:
            destination = _resolve_dir(destination_dir, "read")
            snapshots = [{"path": str(path), "size_bytes": path.stat().st_size} for path in sorted(destination.glob("*snapshot*.zip"))]
        except PolicyError as exc:
            audit("backup.list_backup_snapshots", False, {"destination_dir": destination_dir, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "destination_dir": str(destination), "count": len(snapshots), "snapshots": snapshots}
