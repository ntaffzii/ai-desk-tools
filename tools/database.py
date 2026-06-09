"""Database surface inspection MCP tools.

These tools inspect schema files, migrations, ORM models, and database config
hints without connecting to a database or mutating files.
"""

from __future__ import annotations

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

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".sql", ".prisma"}
SCHEMA_NAMES = {
    "schema.prisma": "prisma",
    "schema.sql": "sql-schema",
    "structure.sql": "sql-schema",
    "database.sql": "sql-schema",
}
MIGRATION_DIR_HINTS = {"migration", "migrations", "alembic", "versions"}
MODEL_FILE_HINTS = {"model", "models", "entity", "entities", "schema", "schemas"}

SQL_TABLE_PATTERN = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?([A-Za-z_][A-Za-z0-9_]*)[\"`]?", re.IGNORECASE)
PRISMA_MODEL_PATTERN = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", re.MULTILINE)
PY_MODEL_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\([^)]*(?:Model|Base)[^)]*\):")
SQLALCHEMY_TABLE_PATTERN = re.compile(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]")
TS_ENTITY_PATTERN = re.compile(r"(?:class|interface|type)\s+([A-Za-z_][A-Za-z0-9_]*(?:Model|Entity|Schema))\b")
DB_ENV_PATTERN = re.compile(r"\b(?:DATABASE_URL|DB_[A-Z0-9_]+|POSTGRES_[A-Z0-9_]+|MYSQL_[A-Z0-9_]+|SQLITE_[A-Z0-9_]+|REDIS_URL|MONGO(?:DB)?_[A-Z0-9_]+)\b")
DB_URL_PATTERN = re.compile(r"\b(?:postgres(?:ql)?|mysql|sqlite|mongodb|redis)://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", re.IGNORECASE)


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


def _parts_lower(path: Path, root: Path) -> set[str]:
    return {part.lower() for part in path.relative_to(root).parts}


def _is_schema_file(path: Path, root: Path) -> bool:
    name = path.name.lower()
    parts = _parts_lower(path, root)
    if name in SCHEMA_NAMES:
        return True
    if path.suffix.lower() == ".prisma":
        return True
    if path.suffix.lower() == ".sql" and ("schema" in name or "database" in name or "db" in parts):
        return True
    return False


def _is_migration_file(path: Path, root: Path) -> bool:
    parts = _parts_lower(path, root)
    return bool(parts & MIGRATION_DIR_HINTS) and path.suffix.lower() in SOURCE_SUFFIXES


def _is_model_file(path: Path, root: Path) -> bool:
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        return False
    stem = path.stem.lower()
    parts = _parts_lower(path, root)
    return stem in MODEL_FILE_HINTS or bool(parts & MODEL_FILE_HINTS)


def _schema_kind(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".prisma"):
        return "prisma"
    if name.endswith(".sql"):
        return "sql"
    if name.endswith(".py"):
        return "python-orm"
    if path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return "javascript-orm"
    return "schema"


def _extract_schema_objects(path: Path, root: Path) -> list[dict]:
    try:
        content = _read_limited(path)
    except OSError:
        return []

    objects = []
    relative_file = str(path.relative_to(root))
    for match in SQL_TABLE_PATTERN.finditer(content):
        objects.append({"file": str(path), "relative_file": relative_file, "kind": "table", "name": match.group(1), "source": "sql"})
    for match in PRISMA_MODEL_PATTERN.finditer(content):
        objects.append({"file": str(path), "relative_file": relative_file, "kind": "model", "name": match.group(1), "source": "prisma"})
    for match in PY_MODEL_PATTERN.finditer(content):
        objects.append({"file": str(path), "relative_file": relative_file, "kind": "model", "name": match.group(1), "source": "python-class"})
    for match in SQLALCHEMY_TABLE_PATTERN.finditer(content):
        objects.append({"file": str(path), "relative_file": relative_file, "kind": "table", "name": match.group(1), "source": "sqlalchemy-tablename"})
    for match in TS_ENTITY_PATTERN.finditer(content):
        objects.append({"file": str(path), "relative_file": relative_file, "kind": "model", "name": match.group(1), "source": "typescript-entity"})
    return objects


def register(mcp) -> None:
    """Register database inspection tools."""

    @mcp.tool()
    def find_database_files(project_path: str | None = None, max_depth: int = 8, limit: int = 100) -> dict:
        """Find likely database schema, migration, and ORM model files."""
        try:
            root = _resolve_project(project_path)
            safe_limit = max(1, min(int(limit), 300))
            files = []
            for path in _iter_files(root, max_depth=max_depth):
                roles = []
                if _is_schema_file(path, root):
                    roles.append("schema")
                if _is_migration_file(path, root):
                    roles.append("migration")
                if _is_model_file(path, root):
                    roles.append("model")
                if roles:
                    files.append({"path": str(path), "relative_path": str(path.relative_to(root)), "kind": _schema_kind(path), "roles": roles, "size_bytes": path.stat().st_size})
                    if len(files) >= safe_limit:
                        break
        except PolicyError as exc:
            audit("database.find_database_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("database.find_database_files", True, {"project_path": str(root), "count": len(files)})
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def extract_schema_objects(project_path: str | None = None, max_depth: int = 8, limit: int = 200) -> dict:
        """Extract likely tables and ORM models from schema/model/migration files."""
        try:
            root = _resolve_project(project_path)
            safe_limit = max(1, min(int(limit), 500))
            objects = []
            for path in _iter_files(root, max_depth=max_depth):
                if not (_is_schema_file(path, root) or _is_migration_file(path, root) or _is_model_file(path, root)):
                    continue
                objects.extend(_extract_schema_objects(path, root))
                if len(objects) >= safe_limit:
                    objects = objects[:safe_limit]
                    break
        except PolicyError as exc:
            audit("database.extract_schema_objects", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("database.extract_schema_objects", True, {"project_path": str(root), "count": len(objects)})
        return {"success": True, "project_path": str(root), "count": len(objects), "objects": objects}

    @mcp.tool()
    def find_migrations(project_path: str | None = None, max_depth: int = 8, limit: int = 120) -> dict:
        """Find migration files and return them in path order."""
        try:
            root = _resolve_project(project_path)
            safe_limit = max(1, min(int(limit), 300))
            migrations = []
            for path in sorted(_iter_files(root, max_depth=max_depth), key=lambda item: str(item).lower()):
                if _is_migration_file(path, root):
                    migrations.append({"path": str(path), "relative_path": str(path.relative_to(root)), "kind": _schema_kind(path), "size_bytes": path.stat().st_size})
                    if len(migrations) >= safe_limit:
                        break
        except PolicyError as exc:
            audit("database.find_migrations", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("database.find_migrations", True, {"project_path": str(root), "count": len(migrations)})
        return {"success": True, "project_path": str(root), "count": len(migrations), "migrations": migrations}

    @mcp.tool()
    def find_database_config(project_path: str | None = None, max_depth: int = 6, limit: int = 80) -> dict:
        """Find database-related env keys and URL hints without revealing env values wholesale."""
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
                env_keys = sorted(set(DB_ENV_PATTERN.findall(content)))[:50]
                db_urls = sorted(set(DB_URL_PATTERN.findall(content)))[:20]
                if env_keys or db_urls:
                    hints.append({"path": str(path), "relative_path": str(path.relative_to(root)), "env_keys": env_keys, "db_url_hints": db_urls})
                if len(hints) >= safe_limit:
                    break
        except PolicyError as exc:
            audit("database.find_database_config", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        audit("database.find_database_config", True, {"project_path": str(root), "count": len(hints)})
        return {"success": True, "project_path": str(root), "count": len(hints), "hints": hints}

    @mcp.tool()
    def summarize_database_surface(project_path: str | None = None) -> dict:
        """Return a lightweight database surface summary without connecting to the database."""
        try:
            root = _resolve_project(project_path)
            files = find_database_files(str(root))
            objects = extract_schema_objects(str(root))
            migrations = find_migrations(str(root))
            config = find_database_config(str(root))
            warnings = []
            if files.get("count", 0) == 0:
                warnings.append("No likely database schema, migration, or model files found")
            if objects.get("count", 0) == 0 and files.get("count", 0) > 0:
                warnings.append("Database files found but no schema objects were extracted")
            if config.get("count", 0) == 0:
                warnings.append("No database config or env key hints found")
        except PolicyError as exc:
            audit("database.summarize_database_surface", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        result = {
            "success": True,
            "project_path": str(root),
            "database_file_count": files.get("count", 0),
            "schema_object_count": objects.get("count", 0),
            "migration_count": migrations.get("count", 0),
            "config_hint_count": config.get("count", 0),
            "warnings": warnings,
        }
        audit("database.summarize_database_surface", True, {"project_path": str(root), "warning_count": len(warnings)})
        return result
