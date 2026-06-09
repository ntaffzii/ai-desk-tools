"""Lightweight repository indexing MCP tools.

These tools build an in-memory index from filenames, small text snippets, and
simple symbols. They do not write cache files or use embeddings.
"""

from __future__ import annotations

import os
import re
from collections import Counter
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
    "dist",
    "build",
    ".next",
    ".turbo",
}
TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".mdx",
    ".txt",
    ".css",
    ".html",
    ".sql",
}
SYMBOL_PATTERNS = [
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)\b", re.MULTILINE),
]


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int, max_files: int):
    count = 0
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in sorted(files):
            path = current / name
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def _safe_read(path: Path, max_chars: int) -> str:
    try:
        if path.stat().st_size > max_chars * 4:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _extract_symbols(text: str, limit: int = 30) -> list[str]:
    symbols = []
    seen = set()
    for pattern in SYMBOL_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                symbols.append(name)
            if len(symbols) >= limit:
                return symbols
    return symbols


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", value) if len(token) >= 2}


def _file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx"}:
        return "source"
    if suffix in {".json", ".yaml", ".yml", ".toml"}:
        return "config"
    if suffix in {".md", ".mdx", ".txt"}:
        return "docs"
    if suffix in {".sql"}:
        return "database"
    if suffix in {".css", ".html"}:
        return "frontend"
    return "text"


def _build_index(root: Path, max_depth: int, max_files: int, max_chars_per_file: int) -> tuple[list[dict], bool]:
    files = []
    truncated = False
    safe_read_limit = min(max(1_000, int(max_chars_per_file)), load_policy().max_file_read_chars)
    safe_max_depth = max(1, min(int(max_depth), 12))
    safe_max_files = max(1, min(int(max_files), 2_000))

    for path in _iter_files(root, safe_max_depth, safe_max_files + 1):
        if len(files) >= safe_max_files:
            truncated = True
            break
        text = _safe_read(path, safe_read_limit)
        relative_path = str(path.relative_to(root))
        symbols = _extract_symbols(text)
        first_lines = [line.strip() for line in text.splitlines()[:4] if line.strip()]
        files.append(
            {
                "path": str(path),
                "relative_path": relative_path,
                "name": path.name,
                "suffix": path.suffix.lower(),
                "kind": _file_kind(path),
                "size_bytes": path.stat().st_size,
                "symbols": symbols,
                "preview": " ".join(first_lines)[:500],
                "token_set": sorted((_tokens(relative_path) | _tokens(" ".join(symbols)) | _tokens(" ".join(first_lines))) - {"the", "and", "for"}),
            }
        )
    return files, truncated


def _score_file(item: dict, query_tokens: set[str], query_lower: str) -> int:
    rel_lower = item["relative_path"].lower()
    symbols_lower = [symbol.lower() for symbol in item["symbols"]]
    symbol_lower = " ".join(symbols_lower)
    preview_lower = item["preview"].lower()
    score = 0
    if query_lower in symbols_lower:
        score += 40
    if query_lower in rel_lower:
        score += 20
    if query_lower in symbol_lower:
        score += 15
    if query_lower in preview_lower:
        score += 8
    token_set = set(item.get("token_set", []))
    score += len(query_tokens & token_set) * 5
    if item["kind"] == "source":
        score += 1
    return score


def register(mcp) -> None:
    """Register repository index tools."""

    @mcp.tool()
    def build_repo_index(project_path: str | None = None, max_depth: int = 6, max_files: int = 500, max_chars_per_file: int = 20_000) -> dict:
        """Build a lightweight in-memory index of project text files."""
        try:
            root = _resolve_project(project_path)
            files, truncated = _build_index(root, max_depth=max_depth, max_files=max_files, max_chars_per_file=max_chars_per_file)
        except PolicyError as exc:
            audit("repo_index.build_repo_index", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        counts_by_kind = Counter(item["kind"] for item in files)
        counts_by_suffix = Counter(item["suffix"] or "[none]" for item in files)
        result = {
            "success": True,
            "project_path": str(root),
            "file_count": len(files),
            "truncated": truncated,
            "counts_by_kind": dict(sorted(counts_by_kind.items())),
            "counts_by_suffix": dict(sorted(counts_by_suffix.items())),
            "files": files,
        }
        audit("repo_index.build_repo_index", True, {"project_path": str(root), "file_count": len(files), "truncated": truncated})
        return result

    @mcp.tool()
    def search_repo_index(query: str, project_path: str | None = None, limit: int = 20) -> dict:
        """Search the lightweight repo index by file name, symbols, and previews."""
        if not query or not query.strip():
            return {"success": False, "error": "empty_query", "message": "query is required"}
        index = build_repo_index(project_path)
        if not index.get("success"):
            return index
        query_lower = query.strip().lower()
        query_tokens = _tokens(query)
        scored = []
        for item in index["files"]:
            score = _score_file(item, query_tokens, query_lower)
            if score > 0:
                scored.append({k: v for k, v in item.items() if k != "token_set"} | {"score": score})
        scored.sort(key=lambda item: (-item["score"], item["relative_path"].lower()))
        safe_limit = max(1, min(int(limit), 100))
        return {"success": True, "project_path": index["project_path"], "query": query, "count": len(scored[:safe_limit]), "matches": scored[:safe_limit]}

    @mcp.tool()
    def find_related_files(file_path: str, project_path: str | None = None, limit: int = 20) -> dict:
        """Find likely related files by shared path tokens, names, suffixes, and symbols."""
        try:
            target = resolve_allowed_path(file_path, access="read")
            root = _resolve_project(project_path) if project_path else target.parent
            if not target.exists() or not target.is_file():
                return {"success": False, "error": "file_not_found", "path": str(target)}
            files, _ = _build_index(root, max_depth=8, max_files=800, max_chars_per_file=20_000)
        except PolicyError as exc:
            audit("repo_index.find_related_files", False, {"file_path": file_path, "project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        target_item = next((item for item in files if Path(item["path"]) == target), None)
        if not target_item:
            target_text = _safe_read(target, 20_000)
            target_item = {
                "relative_path": str(target.relative_to(root)) if target.is_relative_to(root) else target.name,
                "name": target.name,
                "suffix": target.suffix.lower(),
                "kind": _file_kind(target),
                "symbols": _extract_symbols(target_text),
                "token_set": sorted(_tokens(target.name) | _tokens(str(target.parent)) | _tokens(" ".join(_extract_symbols(target_text)))),
            }

        target_tokens = set(target_item.get("token_set", []))
        target_stem = Path(target_item["name"]).stem.lower()
        related = []
        for item in files:
            if Path(item["path"]) == target:
                continue
            score = len(target_tokens & set(item.get("token_set", []))) * 4
            if Path(item["name"]).stem.lower() == target_stem:
                score += 20
            if item["suffix"] == target_item["suffix"]:
                score += 2
            if item["kind"] == target_item["kind"]:
                score += 2
            if score > 0:
                related.append({k: v for k, v in item.items() if k != "token_set"} | {"score": score})
        related.sort(key=lambda item: (-item["score"], item["relative_path"].lower()))
        safe_limit = max(1, min(int(limit), 100))
        return {"success": True, "project_path": str(root), "file_path": str(target), "count": len(related[:safe_limit]), "related_files": related[:safe_limit]}

    @mcp.tool()
    def summarize_index(project_path: str | None = None) -> dict:
        """Summarize repository index shape and useful entry points."""
        index = build_repo_index(project_path, max_depth=6, max_files=800, max_chars_per_file=12_000)
        if not index.get("success"):
            return index
        files = index["files"]
        source_files = [item for item in files if item["kind"] == "source"]
        docs_files = [item for item in files if item["kind"] == "docs"]
        config_files = [item for item in files if item["kind"] == "config"]
        symbol_rich = sorted(source_files, key=lambda item: (-len(item["symbols"]), item["relative_path"].lower()))[:12]
        entry_points = [
            item for item in files if item["name"].lower() in {"readme.md", "package.json", "pyproject.toml", "server.py", "main.py", "app.py"}
        ][:12]
        warnings = []
        if not source_files:
            warnings.append("No source files indexed")
        if not docs_files:
            warnings.append("No docs files indexed")
        return {
            "success": True,
            "project_path": index["project_path"],
            "file_count": index["file_count"],
            "truncated": index["truncated"],
            "counts_by_kind": index["counts_by_kind"],
            "counts_by_suffix": index["counts_by_suffix"],
            "source_file_count": len(source_files),
            "docs_file_count": len(docs_files),
            "config_file_count": len(config_files),
            "entry_points": [{k: v for k, v in item.items() if k != "token_set"} for item in entry_points],
            "symbol_rich_files": [{k: v for k, v in item.items() if k != "token_set"} for item in symbol_rich],
            "warnings": warnings,
        }
