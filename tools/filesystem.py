"""Filesystem MCP tools.

These tools inspect project files without making changes.
Use code_editing.py for write operations.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from security import PolicyError, audit, load_policy, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "$recycle.bin",
}


def _resolve(path: str) -> Path:
    return resolve_allowed_path(path, access="read")


def _split_patterns(patterns: str) -> list[str]:
    return [p.strip() for p in patterns.split(",") if p.strip()] or ["*"]


def _iter_files(root: Path, file_pattern: str = "*", max_file_size: int = 1_000_000):
    patterns = _split_patterns(file_pattern)
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS]
        for name in files:
            if not any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
                continue
            path = Path(current_root) / name
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue
            yield path


def _build_tree(path: Path, max_depth: int, current_depth: int = 1, prefix: str = "") -> str:
    if current_depth > max_depth:
        return f"{prefix}... (depth limit {max_depth})\n"

    try:
        items = sorted(
            [item for item in path.iterdir() if item.name.lower() not in IGNORED_DIRS],
            key=lambda item: (item.is_file(), item.name.lower()),
        )
    except PermissionError:
        return f"{prefix}[permission denied]\n"
    except OSError as exc:
        return f"{prefix}[error: {exc}]\n"

    lines = []
    for index, item in enumerate(items):
        is_last = index == len(items) - 1
        connector = "`-- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
        if item.is_dir():
            child_prefix = prefix + ("    " if is_last else "|   ")
            lines.append(_build_tree(item, max_depth, current_depth + 1, child_prefix).rstrip())
    return "\n".join(line for line in lines if line) + ("\n" if lines else "")


def register(mcp) -> None:
    """Register filesystem tools."""

    @mcp.tool()
    def list_directory_tree(target_path: str, max_depth: int = 3) -> dict:
        """Return a readable directory tree for a folder."""
        try:
            path = _resolve(target_path)
            max_depth = min(max(1, max_depth), 8)
        except PolicyError as exc:
            audit("filesystem.list_directory_tree", False, {"path": target_path, "error": exc.code})
            return policy_error_result(exc)

        if not path.exists():
            audit("filesystem.list_directory_tree", False, {"path": str(path), "error": "path_not_found"})
            return {"success": False, "error": "path_not_found", "path": str(path)}
        if not path.is_dir():
            audit("filesystem.list_directory_tree", False, {"path": str(path), "error": "not_a_directory"})
            return {"success": False, "error": "not_a_directory", "path": str(path)}

        audit("filesystem.list_directory_tree", True, {"path": str(path), "max_depth": max_depth})
        return {
            "success": True,
            "path": str(path),
            "max_depth": max_depth,
            "tree": _build_tree(path, max_depth),
        }

    @mcp.tool()
    def list_files(root: str, pattern: str = "*", limit: int = 100) -> dict:
        """List files under a folder, skipping common dependency/cache folders."""
        try:
            path = _resolve(root)
            limit = min(max(1, limit), 500)
        except PolicyError as exc:
            audit("filesystem.list_files", False, {"root": root, "error": exc.code})
            return policy_error_result(exc)

        if not path.exists():
            audit("filesystem.list_files", False, {"root": str(path), "error": "path_not_found"})
            return {"success": False, "error": "path_not_found", "path": str(path)}
        if not path.is_dir():
            audit("filesystem.list_files", False, {"root": str(path), "error": "not_a_directory"})
            return {"success": False, "error": "not_a_directory", "path": str(path)}

        files = []
        for file_path in _iter_files(path, pattern):
            files.append(str(file_path))
            if len(files) >= limit:
                break

        audit("filesystem.list_files", True, {"root": str(path), "pattern": pattern, "count": len(files)})
        return {"success": True, "root": str(path), "pattern": pattern, "count": len(files), "files": files}

    @mcp.tool()
    def read_file(path: str, max_chars: int = 50_000) -> dict:
        """Read a UTF-8 text file with a size guard."""
        try:
            file_path = _resolve(path)
            max_chars = min(max(1_000, max_chars), load_policy().max_file_read_chars)
        except PolicyError as exc:
            audit("filesystem.read_file", False, {"path": path, "error": exc.code})
            return policy_error_result(exc)

        if not file_path.exists():
            audit("filesystem.read_file", False, {"path": str(file_path), "error": "file_not_found"})
            return {"success": False, "error": "file_not_found", "path": str(file_path)}
        if file_path.is_dir():
            audit("filesystem.read_file", False, {"path": str(file_path), "error": "is_directory"})
            return {"success": False, "error": "is_directory", "path": str(file_path)}

        text = file_path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_chars
        audit("filesystem.read_file", True, {"path": str(file_path), "chars": min(len(text), max_chars), "truncated": truncated})
        return {
            "success": True,
            "path": str(file_path),
            "chars": min(len(text), max_chars),
            "truncated": truncated,
            "content": text[:max_chars],
        }

    @mcp.tool()
    def file_info(path: str) -> dict:
        """Return basic metadata for a file or folder."""
        try:
            target = _resolve(path)
        except PolicyError as exc:
            audit("filesystem.file_info", False, {"path": path, "error": exc.code})
            return policy_error_result(exc)
        if not target.exists():
            audit("filesystem.file_info", False, {"path": str(target), "error": "path_not_found"})
            return {"success": False, "error": "path_not_found", "path": str(target)}

        stat = target.stat()
        audit("filesystem.file_info", True, {"path": str(target)})
        return {
            "success": True,
            "path": str(target),
            "is_file": target.is_file(),
            "is_dir": target.is_dir(),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
        }

    @mcp.tool()
    def find_files_by_keyword(root_path: str, keyword: str, file_pattern: str = "*", limit: int = 50) -> dict:
        """Find files whose names contain a keyword."""
        try:
            root = _resolve(root_path)
            limit = min(max(1, limit), 200)
            keyword_lower = keyword.lower()
        except PolicyError as exc:
            audit("filesystem.find_files_by_keyword", False, {"root": root_path, "error": exc.code})
            return policy_error_result(exc)

        if not root.exists() or not root.is_dir():
            audit("filesystem.find_files_by_keyword", False, {"root": str(root), "error": "invalid_root"})
            return {"success": False, "error": "invalid_root", "root": str(root)}

        matches = []
        for file_path in _iter_files(root, file_pattern):
            if keyword_lower in file_path.name.lower():
                matches.append(str(file_path))
                if len(matches) >= limit:
                    break

        audit("filesystem.find_files_by_keyword", True, {"root": str(root), "keyword": keyword, "count": len(matches)})
        return {"success": True, "root": str(root), "keyword": keyword, "count": len(matches), "matches": matches}

    @mcp.tool()
    def search_in_files(
        root_path: str,
        query: str,
        file_pattern: str = "*",
        is_regex: bool = False,
        case_insensitive: bool = True,
        max_matches: int = 50,
    ) -> dict:
        """Search text inside files recursively."""
        try:
            root = _resolve(root_path)
            max_matches = min(max(1, max_matches), 200)
        except PolicyError as exc:
            audit("filesystem.search_in_files", False, {"root": root_path, "error": exc.code})
            return policy_error_result(exc)

        if not root.exists() or not root.is_dir():
            audit("filesystem.search_in_files", False, {"root": str(root), "error": "invalid_root"})
            return {"success": False, "error": "invalid_root", "root": str(root)}

        if is_regex:
            flags = re.IGNORECASE if case_insensitive else 0
            try:
                compiled = re.compile(query, flags)
            except re.error as exc:
                audit("filesystem.search_in_files", False, {"root": str(root), "error": "invalid_regex"})
                return {"success": False, "error": "invalid_regex", "message": str(exc)}
        else:
            needle = query.lower() if case_insensitive else query

        matches = []
        for file_path in _iter_files(root, file_pattern):
            try:
                with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line_no, line in enumerate(handle, 1):
                        haystack = line if not case_insensitive else line.lower()
                        found = bool(compiled.search(line)) if is_regex else needle in haystack
                        if found:
                            matches.append(
                                {
                                    "file": str(file_path),
                                    "relative_file": str(file_path.relative_to(root)),
                                    "line": line_no,
                                    "text": line.strip(),
                                }
                            )
                            if len(matches) >= max_matches:
                                audit("filesystem.search_in_files", True, {"root": str(root), "query": query, "count": len(matches), "truncated": True})
                                return {"success": True, "root": str(root), "query": query, "matches": matches}
            except OSError:
                continue

        audit("filesystem.search_in_files", True, {"root": str(root), "query": query, "count": len(matches), "truncated": False})
        return {"success": True, "root": str(root), "query": query, "matches": matches}

    @mcp.tool()
    def search_files(root: str, query: str, file_pattern: str = "*", max_matches: int = 50) -> dict:
        """Alias for search_in_files using plain text search."""
        return search_in_files(root, query, file_pattern, False, True, max_matches)
