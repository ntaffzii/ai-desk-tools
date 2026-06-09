"""Documentation and context MCP tools.

These tools are read-only helpers for finding README files, docs folders,
architecture notes, and other project documentation before an agent edits code.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from security import PolicyError, audit, load_policy, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
}

DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".adoc"}
SPECIAL_DOC_PREFIXES = (
    "readme",
    "architecture",
    "adr",
    "changelog",
    "contributing",
    "license",
    "security",
    "code_of_conduct",
)


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _relative_depth(root: Path, path: Path) -> int:
    try:
        return len(path.relative_to(root).parts)
    except ValueError:
        return 999


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in IGNORED_DIRS for part in parts)


def _doc_kind(path: Path, root: Path) -> str:
    name = path.name.lower()
    rel_parts = path.relative_to(root).parts
    parent_parts = {part.lower() for part in rel_parts[:-1]}

    if name.startswith("readme"):
        return "readme"
    if name.startswith("architecture") or "architecture" in parent_parts:
        return "architecture"
    if name.startswith("adr") or "adr" in parent_parts or "adrs" in parent_parts:
        return "adr"
    if name.startswith("changelog"):
        return "changelog"
    if name.startswith("contributing"):
        return "contributing"
    if name.startswith("license"):
        return "license"
    if name.startswith("security"):
        return "security"
    if "docs" in parent_parts or "documentation" in parent_parts:
        return "docs"
    return "markdown" if path.suffix.lower() in {".md", ".mdx"} else "text"


def _is_doc_file(path: Path, root: Path) -> bool:
    if not path.is_file() or _is_ignored(path, root):
        return False
    lower_name = path.name.lower()
    if path.suffix.lower() in DOC_SUFFIXES:
        return True
    return any(lower_name.startswith(prefix) for prefix in SPECIAL_DOC_PREFIXES)


def _find_docs(root: Path, max_depth: int, limit: int) -> list[dict]:
    docs: list[dict] = []
    max_depth = max(1, min(int(max_depth), 12))
    limit = max(1, min(int(limit), 200))

    for path in sorted(root.rglob("*")):
        if len(docs) >= limit:
            break
        if _relative_depth(root, path) > max_depth:
            continue
        if _is_doc_file(path, root):
            stat = path.stat()
            docs.append(
                {
                    "path": str(path),
                    "relative_path": str(path.relative_to(root)),
                    "kind": _doc_kind(path, root),
                    "size_bytes": stat.st_size,
                }
            )
    return docs


def _read_text(path: Path, max_chars: int) -> tuple[str, bool]:
    policy = load_policy()
    safe_limit = max(1, min(int(max_chars), policy.max_file_read_chars))
    content = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(content) > safe_limit
    return content[:safe_limit], truncated


def _score_for_context(doc: dict) -> tuple[int, int, str]:
    priority = {
        "readme": 0,
        "architecture": 1,
        "adr": 2,
        "contributing": 3,
        "docs": 4,
        "security": 5,
        "changelog": 6,
        "license": 7,
        "markdown": 8,
        "text": 9,
    }.get(doc["kind"], 10)
    normalized_path = doc["relative_path"].replace("\\", "/")
    return priority, len(normalized_path.split("/")), normalized_path.lower()


def register(mcp) -> None:
    """Register documentation/context tools."""

    @mcp.tool()
    def find_documentation(project_path: str | None = None, max_depth: int = 4, limit: int = 80) -> dict:
        """Find README, docs, architecture notes, and related documentation files."""
        try:
            root = _resolve_project(project_path)
            docs = _find_docs(root, max_depth=max_depth, limit=limit)
        except PolicyError as exc:
            audit("docs.find_documentation", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            audit("docs.find_documentation", False, {"project_path": project_path, "error": str(exc)})
            return {"success": False, "error": "filesystem_error", "message": str(exc)}

        result = {"success": True, "project_path": str(root), "count": len(docs), "documents": docs}
        audit("docs.find_documentation", True, {"project_path": str(root), "count": len(docs)})
        return result

    @mcp.tool()
    def read_documentation_file(file_path: str, max_chars: int = 50_000) -> dict:
        """Read one documentation file inside the allowed roots."""
        try:
            path = resolve_allowed_path(file_path, access="read")
            if not path.exists():
                raise PolicyError("path_not_found", "documentation file does not exist", {"path": str(path)})
            if not path.is_file():
                raise PolicyError("path_not_file", "documentation path must be a file", {"path": str(path)})
            content, truncated = _read_text(path, max_chars=max_chars)
        except PolicyError as exc:
            audit("docs.read_documentation_file", False, {"file_path": file_path, "error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            audit("docs.read_documentation_file", False, {"file_path": file_path, "error": str(exc)})
            return {"success": False, "error": "filesystem_error", "message": str(exc)}

        result = {
            "success": True,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "truncated": truncated,
            "content": content,
        }
        audit("docs.read_documentation_file", True, {"path": str(path), "truncated": truncated})
        return result

    @mcp.tool()
    def summarize_documentation_index(project_path: str | None = None, max_depth: int = 4) -> dict:
        """Summarize documentation coverage and gaps without reading full file bodies."""
        try:
            root = _resolve_project(project_path)
            docs = _find_docs(root, max_depth=max_depth, limit=200)
        except PolicyError as exc:
            audit("docs.summarize_documentation_index", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            audit("docs.summarize_documentation_index", False, {"project_path": project_path, "error": str(exc)})
            return {"success": False, "error": "filesystem_error", "message": str(exc)}

        counts = Counter(doc["kind"] for doc in docs)
        warnings = []
        if counts.get("readme", 0) == 0:
            warnings.append("README not found")
        if counts.get("architecture", 0) == 0 and counts.get("adr", 0) == 0:
            warnings.append("Architecture notes or ADRs not found")
        if counts.get("docs", 0) == 0:
            warnings.append("docs/ documentation not found")

        result = {
            "success": True,
            "project_path": str(root),
            "total_documents": len(docs),
            "counts_by_kind": dict(sorted(counts.items())),
            "entry_points": [doc for doc in sorted(docs, key=_score_for_context)[:12]],
            "warnings": warnings,
        }
        audit("docs.summarize_documentation_index", True, {"project_path": str(root), "warning_count": len(warnings)})
        return result

    @mcp.tool()
    def build_context_bundle(
        project_path: str | None = None,
        max_files: int = 8,
        max_chars_per_file: int = 12_000,
    ) -> dict:
        """Build a compact documentation bundle for an agent to read before a task."""
        try:
            root = _resolve_project(project_path)
            docs = sorted(_find_docs(root, max_depth=5, limit=200), key=_score_for_context)
            selected = docs[: max(1, min(int(max_files), 20))]
            files = []
            for doc in selected:
                path = Path(doc["path"])
                content, truncated = _read_text(path, max_chars=max_chars_per_file)
                files.append({**doc, "truncated": truncated, "content": content})
        except PolicyError as exc:
            audit("docs.build_context_bundle", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            audit("docs.build_context_bundle", False, {"project_path": project_path, "error": str(exc)})
            return {"success": False, "error": "filesystem_error", "message": str(exc)}

        result = {
            "success": True,
            "project_path": str(root),
            "selected_count": len(files),
            "available_count": len(docs),
            "files": files,
        }
        audit("docs.build_context_bundle", True, {"project_path": str(root), "selected_count": len(files)})
        return result

    @mcp.tool()
    def find_docs_by_keyword(
        keyword: str,
        project_path: str | None = None,
        max_depth: int = 5,
        limit: int = 40,
        context_chars: int = 160,
    ) -> dict:
        """Search documentation files for a keyword and return small context snippets."""
        if not keyword or not keyword.strip():
            return {"success": False, "error": "empty_keyword", "message": "keyword is required"}

        needle = keyword.strip().lower()
        try:
            root = _resolve_project(project_path)
            docs = _find_docs(root, max_depth=max_depth, limit=200)
            matches = []
            safe_limit = max(1, min(int(limit), 100))
            safe_context_chars = max(0, min(int(context_chars), 2_000))
            for doc in docs:
                path = Path(doc["path"])
                content, _ = _read_text(path, max_chars=load_policy().max_file_read_chars)
                idx = content.lower().find(needle)
                if idx < 0:
                    continue
                start = max(0, idx - safe_context_chars)
                end = min(len(content), idx + len(keyword) + safe_context_chars)
                matches.append({**doc, "snippet": content[start:end].strip()})
                if len(matches) >= safe_limit:
                    break
        except PolicyError as exc:
            audit("docs.find_docs_by_keyword", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            audit("docs.find_docs_by_keyword", False, {"project_path": project_path, "error": str(exc)})
            return {"success": False, "error": "filesystem_error", "message": str(exc)}

        result = {"success": True, "project_path": str(root), "keyword": keyword, "count": len(matches), "matches": matches}
        audit("docs.find_docs_by_keyword", True, {"project_path": str(root), "count": len(matches)})
        return result
