"""API surface inspection MCP tools.

These tools find likely API route files, OpenAPI specs, endpoint declarations,
and environment/config hints without starting servers or mutating files.
"""

from __future__ import annotations

import json
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
    "dist",
    "build",
    ".next",
    ".turbo",
}

ROUTE_FILE_HINTS = (
    "route",
    "routes",
    "router",
    "api",
    "endpoint",
    "endpoints",
    "controller",
    "controllers",
    "server",
    "app",
    "main",
)

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SPEC_NAMES = {
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
    "swagger.yml",
}

PY_ROUTE_PATTERN = re.compile(r"@\w+(?:\.\w+)*\.(get|post|put|patch|delete|options|head)\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
FLASK_ROUTE_PATTERN = re.compile(r"@\w+\.route\(\s*['\"]([^'\"]+)['\"](?:[^)]*methods\s*=\s*\[([^\]]+)\])?", re.IGNORECASE)
JS_ROUTE_PATTERN = re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete|options|head)\(\s*['\"`]([^'\"`]+)['\"`]", re.IGNORECASE)
NEXT_ROUTE_PATTERN = re.compile(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\b")
URL_PATTERN = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
ENV_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 8, max_file_size: int = 1_000_000):
    max_depth = max(1, min(int(max_depth), 16))
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)
        try:
            rel_depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        if rel_depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            path = current_path / name
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue
            yield path


def _read_limited(path: Path) -> str:
    max_chars = min(load_policy().max_file_read_chars, 200_000)
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]


def _is_route_file(path: Path, root: Path) -> bool:
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        return False
    lowered_parts = [part.lower() for part in path.relative_to(root).parts]
    stem = path.stem.lower()
    return any(hint in lowered_parts or hint in stem for hint in ROUTE_FILE_HINTS)


def _route_file_kind(path: Path, root: Path) -> str:
    rel = [part.lower() for part in path.relative_to(root).parts]
    name = path.name.lower()
    if "api" in rel and name in {"route.ts", "route.js"}:
        return "next-api-route"
    if path.suffix.lower() == ".py":
        return "python-api"
    if path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return "javascript-api"
    return "api-source"


def _extract_endpoints_from_file(path: Path, root: Path) -> list[dict]:
    try:
        content = _read_limited(path)
    except OSError:
        return []

    endpoints = []
    relative_file = str(path.relative_to(root))
    for match in PY_ROUTE_PATTERN.finditer(content):
        endpoints.append({"file": str(path), "relative_file": relative_file, "method": match.group(1).upper(), "path": match.group(2), "source": "python-decorator"})
    for match in FLASK_ROUTE_PATTERN.finditer(content):
        methods_raw = match.group(2) or "'GET'"
        methods = re.findall(r"['\"]([A-Za-z]+)['\"]", methods_raw) or ["GET"]
        for method in methods:
            endpoints.append({"file": str(path), "relative_file": relative_file, "method": method.upper(), "path": match.group(1), "source": "flask-route"})
    for match in JS_ROUTE_PATTERN.finditer(content):
        endpoints.append({"file": str(path), "relative_file": relative_file, "method": match.group(1).upper(), "path": match.group(2), "source": "js-router"})
    if path.name.lower() in {"route.ts", "route.js"}:
        for match in NEXT_ROUTE_PATTERN.finditer(content):
            route_path = "/" + "/".join(part for part in path.relative_to(root).parts[:-1] if part not in {"app", "pages"})
            endpoints.append({"file": str(path), "relative_file": relative_file, "method": match.group(1).upper(), "path": route_path.replace("\\", "/"), "source": "next-route-handler"})
    return endpoints


def _find_specs(root: Path, max_depth: int = 8) -> list[dict]:
    specs = []
    for path in _iter_files(root, max_depth=max_depth):
        if path.name.lower() in SPEC_NAMES:
            specs.append({"path": str(path), "relative_path": str(path.relative_to(root)), "size_bytes": path.stat().st_size})
    return specs


def _parse_json_spec(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    paths = data.get("paths", {})
    if not isinstance(paths, dict):
        paths = {}
    endpoint_count = 0
    for methods in paths.values():
        if isinstance(methods, dict):
            endpoint_count += len([key for key in methods if key.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}])
    return {
        "title": data.get("info", {}).get("title") if isinstance(data.get("info"), dict) else None,
        "version": data.get("info", {}).get("version") if isinstance(data.get("info"), dict) else None,
        "path_count": len(paths),
        "endpoint_count": endpoint_count,
    }


def register(mcp) -> None:
    """Register API inspection tools."""

    @mcp.tool()
    def find_api_files(project_path: str | None = None, max_depth: int = 8, limit: int = 80) -> dict:
        """Find likely API route/controller/server files."""
        try:
            root = _resolve_project(project_path)
            safe_limit = max(1, min(int(limit), 200))
            files = []
            for path in _iter_files(root, max_depth=max_depth):
                if _is_route_file(path, root):
                    files.append({"path": str(path), "relative_path": str(path.relative_to(root)), "kind": _route_file_kind(path, root), "size_bytes": path.stat().st_size})
                    if len(files) >= safe_limit:
                        break
        except PolicyError as exc:
            audit("api.find_api_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("api.find_api_files", True, {"project_path": str(root), "count": len(files)})
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def extract_api_endpoints(project_path: str | None = None, max_depth: int = 8, limit: int = 120) -> dict:
        """Extract likely endpoints from common FastAPI, Flask, Express, and Next route patterns."""
        try:
            root = _resolve_project(project_path)
            safe_limit = max(1, min(int(limit), 300))
            endpoints = []
            for path in _iter_files(root, max_depth=max_depth):
                if not _is_route_file(path, root):
                    continue
                endpoints.extend(_extract_endpoints_from_file(path, root))
                if len(endpoints) >= safe_limit:
                    endpoints = endpoints[:safe_limit]
                    break
        except PolicyError as exc:
            audit("api.extract_api_endpoints", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("api.extract_api_endpoints", True, {"project_path": str(root), "count": len(endpoints)})
        return {"success": True, "project_path": str(root), "count": len(endpoints), "endpoints": endpoints}

    @mcp.tool()
    def find_openapi_specs(project_path: str | None = None, max_depth: int = 8) -> dict:
        """Find OpenAPI/Swagger spec files and summarize JSON specs when possible."""
        try:
            root = _resolve_project(project_path)
            specs = _find_specs(root, max_depth=max_depth)
            for spec in specs:
                if spec["relative_path"].lower().endswith(".json"):
                    spec["summary"] = _parse_json_spec(Path(spec["path"]))
        except PolicyError as exc:
            audit("api.find_openapi_specs", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("api.find_openapi_specs", True, {"project_path": str(root), "count": len(specs)})
        return {"success": True, "project_path": str(root), "count": len(specs), "specs": specs}

    @mcp.tool()
    def find_api_config(project_path: str | None = None, max_depth: int = 6, limit: int = 80) -> dict:
        """Find URL and environment-key hints in likely API/config files."""
        try:
            root = _resolve_project(project_path)
            safe_limit = max(1, min(int(limit), 200))
            hints = []
            for path in _iter_files(root, max_depth=max_depth, max_file_size=500_000):
                lowered = path.name.lower()
                if path.suffix.lower() not in SOURCE_SUFFIXES and not lowered.startswith(".env") and "config" not in lowered:
                    continue
                try:
                    content = _read_limited(path)
                except OSError:
                    continue
                urls = sorted(set(URL_PATTERN.findall(content)))[:20]
                env_keys = sorted(set(ENV_KEY_PATTERN.findall(content)))[:40]
                if urls or env_keys:
                    hints.append({"path": str(path), "relative_path": str(path.relative_to(root)), "urls": urls, "env_keys": env_keys})
                if len(hints) >= safe_limit:
                    break
        except PolicyError as exc:
            audit("api.find_api_config", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("api.find_api_config", True, {"project_path": str(root), "count": len(hints)})
        return {"success": True, "project_path": str(root), "count": len(hints), "hints": hints}

    @mcp.tool()
    def summarize_api_surface(project_path: str | None = None) -> dict:
        """Return a lightweight API surface summary without running the app."""
        try:
            root = _resolve_project(project_path)
            api_files = find_api_files(str(root))
            endpoints = extract_api_endpoints(str(root))
            specs = find_openapi_specs(str(root))
            warnings = []
            if api_files.get("count", 0) == 0:
                warnings.append("No likely API route files found")
            if endpoints.get("count", 0) == 0 and specs.get("count", 0) == 0:
                warnings.append("No endpoints or OpenAPI specs found")
        except PolicyError as exc:
            audit("api.summarize_api_surface", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        result = {
            "success": True,
            "project_path": str(root),
            "api_file_count": api_files.get("count", 0),
            "endpoint_count": endpoints.get("count", 0),
            "openapi_spec_count": specs.get("count", 0),
            "warnings": warnings,
        }
        audit("api.summarize_api_surface", True, {"project_path": str(root), "warning_count": len(warnings)})
        return result
