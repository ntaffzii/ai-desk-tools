"""Structured data inspection and editing MCP tools."""

from __future__ import annotations

import json
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


def _resolve(path: str, access: str = "read") -> Path:
    return resolve_allowed_path(path, access=access)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _path_parts(json_path: str) -> list[str]:
    return [part for part in json_path.strip(".").split(".") if part]


def _get_value(data, json_path: str):
    current = data
    for part in _path_parts(json_path):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def _set_value(data, json_path: str, value):
    parts = _path_parts(json_path)
    current = data
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value


def register(mcp) -> None:
    """Register structured data tools."""

    @mcp.tool()
    def read_json(file_path: str) -> dict:
        """Read a JSON file into structured data."""
        try:
            path = _resolve(file_path)
            data = _load_json(path)
        except PolicyError as exc:
            audit("structured_data.read_json", False, {"file_path": file_path, "error": exc.code})
            return policy_error_result(exc)
        except Exception as exc:
            return {"success": False, "error": "invalid_json", "message": str(exc)}
        return {"success": True, "path": str(path), "data": data}

    @mcp.tool()
    def validate_json(file_path: str) -> dict:
        """Validate JSON syntax."""
        result = read_json(file_path)
        return {"success": result.get("success", False), "path": result.get("path"), "error": result.get("error"), "message": result.get("message")}

    @mcp.tool()
    def get_json_path(file_path: str, json_path: str) -> dict:
        """Read one dot-separated path from a JSON file."""
        result = read_json(file_path)
        if not result.get("success"):
            return result
        try:
            value = _get_value(result["data"], json_path)
        except Exception as exc:
            return {"success": False, "error": "json_path_not_found", "message": str(exc), "json_path": json_path}
        return {"success": True, "path": result["path"], "json_path": json_path, "value": value}

    @mcp.tool()
    def patch_json_path(file_path: str, json_path: str, value_json: str, create_backup: bool = True) -> dict:
        """Set one dot-separated JSON path. value_json must be valid JSON."""
        try:
            path = _resolve(file_path, "write")
            data = _load_json(path)
            value = json.loads(value_json)
            backup_path = None
            if create_backup:
                backup_path = str(path.with_suffix(path.suffix + ".bak"))
                Path(backup_path).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            _set_value(data, json_path, value)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except PolicyError as exc:
            audit("structured_data.patch_json_path", False, {"file_path": file_path, "error": exc.code})
            return policy_error_result(exc)
        except Exception as exc:
            return {"success": False, "error": "json_patch_failed", "message": str(exc)}
        audit("structured_data.patch_json_path", True, {"file_path": str(path), "json_path": json_path})
        return {"success": True, "path": str(path), "json_path": json_path, "backup_path": backup_path}

    @mcp.tool()
    def inspect_toml(file_path: str) -> dict:
        """Read TOML into structured data when Python tomllib is available."""
        if tomllib is None:
            return {"success": False, "error": "tomllib_unavailable"}
        try:
            path = _resolve(file_path)
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except PolicyError as exc:
            return policy_error_result(exc)
        except Exception as exc:
            return {"success": False, "error": "invalid_toml", "message": str(exc)}
        return {"success": True, "path": str(path), "data": data}

    @mcp.tool()
    def read_yaml(file_path: str) -> dict:
        """Read YAML into structured data when PyYAML is available."""
        if yaml is None:
            return {"success": False, "error": "yaml_unavailable", "message": "Install PyYAML to enable YAML parsing."}
        try:
            path = _resolve(file_path)
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except PolicyError as exc:
            audit("structured_data.read_yaml", False, {"file_path": file_path, "error": exc.code})
            return policy_error_result(exc)
        except Exception as exc:
            return {"success": False, "error": "invalid_yaml", "message": str(exc)}
        return {"success": True, "path": str(path), "data": data}

    @mcp.tool()
    def validate_yaml(file_path: str) -> dict:
        """Validate YAML syntax when PyYAML is available."""
        result = read_yaml(file_path)
        return {"success": result.get("success", False), "path": result.get("path"), "error": result.get("error"), "message": result.get("message")}

    @mcp.tool()
    def get_yaml_path(file_path: str, yaml_path: str) -> dict:
        """Read one dot-separated path from a YAML file."""
        result = read_yaml(file_path)
        if not result.get("success"):
            return result
        try:
            value = _get_value(result["data"], yaml_path)
        except Exception as exc:
            return {"success": False, "error": "yaml_path_not_found", "message": str(exc), "yaml_path": yaml_path}
        return {"success": True, "path": result["path"], "yaml_path": yaml_path, "value": value}
