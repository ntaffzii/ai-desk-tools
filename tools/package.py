"""Package and dependency inspection MCP tools.

These tools read package manifests and lockfile signals without installing,
updating, or mutating dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


MANIFESTS = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "composer.json": "php",
    "Gemfile": "ruby",
}

LOCKFILES = {
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv",
    "uv.lock": "uv",
    "Cargo.lock": "cargo",
    "go.sum": "go",
    "composer.lock": "composer",
    "Gemfile.lock": "bundler",
}


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_toml(path: Path) -> dict:
    if tomllib is None:
        return {}
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _requirements(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    packages = []
    for line in lines:
        item = line.strip()
        if not item or item.startswith("#") or item.startswith("-"):
            continue
        packages.append(item)
    return packages


def _manifest_entries(root: Path) -> list[dict]:
    entries = []
    for filename, ecosystem in MANIFESTS.items():
        path = root / filename
        if path.exists():
            entries.append({"file": filename, "ecosystem": ecosystem, "path": str(path), "size_bytes": path.stat().st_size})
    return entries


def _lockfile_entries(root: Path) -> list[dict]:
    entries = []
    for filename, manager in LOCKFILES.items():
        path = root / filename
        if path.exists():
            entries.append({"file": filename, "manager": manager, "path": str(path), "size_bytes": path.stat().st_size})
    return entries


def _node_details(root: Path) -> dict:
    package_json = root / "package.json"
    if not package_json.exists():
        return {}

    data = _safe_json(package_json)
    scripts = data.get("scripts", {})
    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    peer_deps = data.get("peerDependencies", {})
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "package_manager": data.get("packageManager"),
        "type": data.get("type"),
        "scripts": scripts if isinstance(scripts, dict) else {},
        "dependencies": deps if isinstance(deps, dict) else {},
        "dev_dependencies": dev_deps if isinstance(dev_deps, dict) else {},
        "peer_dependencies": peer_deps if isinstance(peer_deps, dict) else {},
    }


def _python_details(root: Path) -> dict:
    details: dict = {}
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = _safe_toml(pyproject)
        project = data.get("project", {}) if isinstance(data.get("project", {}), dict) else {}
        tool = data.get("tool", {}) if isinstance(data.get("tool", {}), dict) else {}
        poetry = tool.get("poetry", {}) if isinstance(tool.get("poetry", {}), dict) else {}
        details["pyproject"] = {
            "name": project.get("name") or poetry.get("name"),
            "version": project.get("version") or poetry.get("version"),
            "dependencies": project.get("dependencies", []),
            "optional_dependencies": project.get("optional-dependencies", {}),
            "poetry_dependencies": poetry.get("dependencies", {}),
            "poetry_dev_dependencies": poetry.get("dev-dependencies", {}),
            "build_system": data.get("build-system", {}),
        }

    requirements = root / "requirements.txt"
    if requirements.exists():
        details["requirements"] = _requirements(requirements)

    return details


def _dependency_counts(node_details: dict, python_details: dict) -> dict:
    counts = {}
    if node_details:
        counts["node_dependencies"] = len(node_details.get("dependencies", {}))
        counts["node_dev_dependencies"] = len(node_details.get("dev_dependencies", {}))
        counts["node_peer_dependencies"] = len(node_details.get("peer_dependencies", {}))
    if python_details:
        pyproject = python_details.get("pyproject", {})
        counts["python_project_dependencies"] = len(pyproject.get("dependencies", []) or [])
        counts["python_optional_dependency_groups"] = len(pyproject.get("optional_dependencies", {}) or {})
        counts["python_poetry_dependencies"] = len(pyproject.get("poetry_dependencies", {}) or {})
        counts["python_requirements"] = len(python_details.get("requirements", []) or [])
    return counts


def register(mcp) -> None:
    """Register package/dependency tools."""

    @mcp.tool()
    def detect_package_managers(project_path: str | None = None) -> dict:
        """Detect package ecosystems, manifests, lockfiles, and likely package managers."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("package.detect_package_managers", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        manifests = _manifest_entries(root)
        lockfiles = _lockfile_entries(root)
        ecosystems = sorted({item["ecosystem"] for item in manifests})
        managers = sorted({item["manager"] for item in lockfiles})
        result = {
            "success": True,
            "project_path": str(root),
            "ecosystems": ecosystems,
            "package_managers": managers,
            "manifests": manifests,
            "lockfiles": lockfiles,
        }
        audit("package.detect_package_managers", True, {"project_path": str(root), "ecosystems": ecosystems, "managers": managers})
        return result

    @mcp.tool()
    def read_package_manifest(project_path: str | None = None) -> dict:
        """Read supported package manifests into structured fields."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("package.read_package_manifest", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        node = _node_details(root)
        python = _python_details(root)
        result = {
            "success": True,
            "project_path": str(root),
            "manifests": _manifest_entries(root),
            "node": node,
            "python": python,
        }
        audit("package.read_package_manifest", True, {"project_path": str(root), "manifest_count": len(result["manifests"])})
        return result

    @mcp.tool()
    def list_dependencies(project_path: str | None = None, include_dev: bool = True) -> dict:
        """List dependency names from supported Node and Python manifests."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("package.list_dependencies", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        node = _node_details(root)
        python = _python_details(root)
        dependencies: list[dict] = []

        for name, version in node.get("dependencies", {}).items():
            dependencies.append({"ecosystem": "node", "scope": "dependencies", "name": name, "version": version})
        if include_dev:
            for name, version in node.get("dev_dependencies", {}).items():
                dependencies.append({"ecosystem": "node", "scope": "devDependencies", "name": name, "version": version})
        for name, version in node.get("peer_dependencies", {}).items():
            dependencies.append({"ecosystem": "node", "scope": "peerDependencies", "name": name, "version": version})

        pyproject = python.get("pyproject", {})
        for item in pyproject.get("dependencies", []) or []:
            dependencies.append({"ecosystem": "python", "scope": "project.dependencies", "name": item, "version": None})
        for item in python.get("requirements", []) or []:
            dependencies.append({"ecosystem": "python", "scope": "requirements.txt", "name": item, "version": None})

        result = {"success": True, "project_path": str(root), "count": len(dependencies), "dependencies": dependencies}
        audit("package.list_dependencies", True, {"project_path": str(root), "count": len(dependencies)})
        return result

    @mcp.tool()
    def get_lockfile_status(project_path: str | None = None) -> dict:
        """Report lockfiles and whether each detected ecosystem has an obvious lockfile."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("package.get_lockfile_status", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        manifests = _manifest_entries(root)
        lockfiles = _lockfile_entries(root)
        ecosystems = {item["ecosystem"] for item in manifests}
        managers = {item["manager"] for item in lockfiles}
        status = {
            "node": bool({"npm", "yarn", "pnpm"} & managers) if "node" in ecosystems else None,
            "python": bool({"poetry", "pipenv", "uv"} & managers) if "python" in ecosystems else None,
            "rust": "cargo" in managers if "rust" in ecosystems else None,
            "go": "go" in managers if "go" in ecosystems else None,
            "php": "composer" in managers if "php" in ecosystems else None,
            "ruby": "bundler" in managers if "ruby" in ecosystems else None,
        }
        warnings = [f"{ecosystem} manifest detected without obvious lockfile" for ecosystem, has_lock in status.items() if has_lock is False]
        result = {"success": True, "project_path": str(root), "lockfiles": lockfiles, "status": status, "warnings": warnings}
        audit("package.get_lockfile_status", True, {"project_path": str(root), "warning_count": len(warnings)})
        return result

    @mcp.tool()
    def summarize_dependency_health(project_path: str | None = None) -> dict:
        """Return a lightweight dependency health summary without installing packages."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("package.summarize_dependency_health", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        node = _node_details(root)
        python = _python_details(root)
        manifests = _manifest_entries(root)
        lock_status = get_lockfile_status(str(root))
        warnings = []
        if not manifests:
            warnings.append("No supported package manifest found")
        warnings.extend(lock_status.get("warnings", []))
        if node and not node.get("scripts"):
            warnings.append("package.json has no scripts")

        result = {
            "success": True,
            "project_path": str(root),
            "manifest_count": len(manifests),
            "lockfile_count": len(_lockfile_entries(root)),
            "dependency_counts": _dependency_counts(node, python),
            "warnings": warnings,
        }
        audit("package.summarize_dependency_health", True, {"project_path": str(root), "warning_count": len(warnings)})
        return result
