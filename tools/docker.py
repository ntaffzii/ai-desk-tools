"""Docker project inspection MCP tools.

These tools are read-only. They inspect Docker-related files and plan
validation commands without building images, starting containers, or touching
the Docker daemon.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
DOCKERFILE_NAMES = {"Dockerfile", "Containerfile"}
COMPOSE_NAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 5):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            yield current / name


def _is_dockerfile(path: Path) -> bool:
    return path.name in DOCKERFILE_NAMES or path.name.startswith("Dockerfile.")


def _is_compose_file(path: Path) -> bool:
    return path.name in COMPOSE_NAMES


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _inspect_dockerfile(path: Path, root: Path) -> dict:
    text = _read(path)
    instructions = []
    stages = []
    exposes = []
    workdirs = []
    copies = []
    run_count = 0
    cmd = None
    entrypoint = None

    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw_line)
        if not line:
            continue
        match = re.match(r"^([A-Za-z]+)\s+(.*)$", line)
        if not match:
            continue
        instruction = match.group(1).upper()
        value = match.group(2).strip()
        instructions.append({"line": line_no, "instruction": instruction, "value": value})
        if instruction == "FROM":
            stage_match = re.match(r"(.+?)\s+AS\s+(.+)$", value, flags=re.IGNORECASE)
            stages.append({"line": line_no, "image": (stage_match.group(1) if stage_match else value).strip(), "name": stage_match.group(2).strip() if stage_match else None})
        elif instruction == "EXPOSE":
            exposes.extend(value.split())
        elif instruction == "WORKDIR":
            workdirs.append(value)
        elif instruction in {"COPY", "ADD"}:
            copies.append({"line": line_no, "instruction": instruction, "value": value})
        elif instruction == "RUN":
            run_count += 1
        elif instruction == "CMD":
            cmd = value
        elif instruction == "ENTRYPOINT":
            entrypoint = value

    warnings = []
    if not stages:
        warnings.append("No FROM instruction found")
    if any(stage["image"].lower().endswith(":latest") or ":" not in stage["image"] for stage in stages):
        warnings.append("Base image tag may be floating or implicit")
    if not cmd and not entrypoint:
        warnings.append("No CMD or ENTRYPOINT found")

    return {
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "stages": stages,
        "exposes": exposes,
        "workdirs": workdirs,
        "copy_like_count": len(copies),
        "run_count": run_count,
        "cmd": cmd,
        "entrypoint": entrypoint,
        "instruction_count": len(instructions),
        "warnings": warnings,
    }


def _inspect_compose(path: Path, root: Path) -> dict:
    text = _read(path)
    services = []
    current_service = None
    in_services = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services:
            service_match = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
            if service_match:
                current_service = {"name": service_match.group(1), "image": None, "build": None, "ports": []}
                services.append(current_service)
                continue
            if current_service:
                image_match = re.match(r"^\s{4}image:\s*(.+)$", line)
                build_match = re.match(r"^\s{4}build:\s*(.+)?$", line)
                port_match = re.match(r"^\s{6}-\s*[\"']?([^\"']+)[\"']?\s*$", line)
                if image_match:
                    current_service["image"] = image_match.group(1).strip()
                elif build_match:
                    current_service["build"] = (build_match.group(1) or ".").strip()
                elif "ports:" in line:
                    continue
                elif port_match:
                    current_service["ports"].append(port_match.group(1).strip())
            if line and not line.startswith(" "):
                in_services = False

    warnings = []
    if not services:
        warnings.append("No services detected")
    for service in services:
        if not service.get("image") and not service.get("build"):
            warnings.append(f"Service {service['name']} has no image or build hint")

    return {
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "service_count": len(services),
        "services": services,
        "warnings": warnings,
    }


def register(mcp) -> None:
    """Register Docker inspection tools."""

    @mcp.tool()
    def check_docker_available() -> dict:
        """Check whether Docker CLI commands are available on PATH."""
        docker = shutil.which("docker")
        compose = shutil.which("docker-compose")
        result = {
            "success": True,
            "docker_cli": docker,
            "docker_compose_cli": compose,
            "compose_subcommand_command": "docker compose",
            "can_plan_only": True,
        }
        audit("docker.check_docker_available", True, {"docker_cli_present": bool(docker), "docker_compose_present": bool(compose)})
        return result

    @mcp.tool()
    def find_docker_files(project_path: str | None = None, max_depth: int = 5) -> dict:
        """Find Dockerfile and Compose files inside a project."""
        try:
            root = _resolve_project(project_path)
            dockerfiles = []
            compose_files = []
            for path in _iter_files(root, max_depth=max_depth):
                if _is_dockerfile(path):
                    dockerfiles.append({"path": str(path), "relative_path": str(path.relative_to(root))})
                elif _is_compose_file(path):
                    compose_files.append({"path": str(path), "relative_path": str(path.relative_to(root))})
        except PolicyError as exc:
            audit("docker.find_docker_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        result = {
            "success": True,
            "project_path": str(root),
            "dockerfile_count": len(dockerfiles),
            "compose_file_count": len(compose_files),
            "dockerfiles": dockerfiles,
            "compose_files": compose_files,
        }
        audit("docker.find_docker_files", True, {"project_path": str(root), "count": len(dockerfiles) + len(compose_files)})
        return result

    @mcp.tool()
    def inspect_dockerfile(project_path: str | None = None, dockerfile_path: str | None = None) -> dict:
        """Inspect Dockerfile stages, exposed ports, commands, and risk hints."""
        try:
            root = _resolve_project(project_path)
            if dockerfile_path:
                path = resolve_allowed_path(dockerfile_path, access="read")
            else:
                files = find_docker_files(str(root))
                if not files.get("success"):
                    return files
                if not files["dockerfiles"]:
                    return {"success": False, "error": "dockerfile_not_found", "project_path": str(root)}
                path = Path(files["dockerfiles"][0]["path"])
            if not path.exists() or not path.is_file():
                return {"success": False, "error": "dockerfile_not_found", "path": str(path)}
            result = {"success": True, "project_path": str(root), "dockerfile": _inspect_dockerfile(path, root)}
        except PolicyError as exc:
            audit("docker.inspect_dockerfile", False, {"project_path": project_path, "dockerfile_path": dockerfile_path, "error": exc.code})
            return policy_error_result(exc)
        audit("docker.inspect_dockerfile", True, {"project_path": str(root), "path": str(path)})
        return result

    @mcp.tool()
    def inspect_docker_compose(project_path: str | None = None, compose_path: str | None = None) -> dict:
        """Inspect Docker Compose services, image/build hints, and ports."""
        try:
            root = _resolve_project(project_path)
            if compose_path:
                path = resolve_allowed_path(compose_path, access="read")
            else:
                files = find_docker_files(str(root))
                if not files.get("success"):
                    return files
                if not files["compose_files"]:
                    return {"success": False, "error": "compose_file_not_found", "project_path": str(root)}
                path = Path(files["compose_files"][0]["path"])
            if not path.exists() or not path.is_file():
                return {"success": False, "error": "compose_file_not_found", "path": str(path)}
            result = {"success": True, "project_path": str(root), "compose": _inspect_compose(path, root)}
        except PolicyError as exc:
            audit("docker.inspect_docker_compose", False, {"project_path": project_path, "compose_path": compose_path, "error": exc.code})
            return policy_error_result(exc)
        audit("docker.inspect_docker_compose", True, {"project_path": str(root), "path": str(path)})
        return result

    @mcp.tool()
    def plan_docker_validation(project_path: str | None = None) -> dict:
        """Plan safe Docker validation commands without executing them."""
        files = find_docker_files(project_path)
        if not files.get("success"):
            return files
        commands = []
        for item in files["dockerfiles"]:
            commands.append({"purpose": "Validate Dockerfile syntax/build context", "command": f"docker build --check -f {item['relative_path']} .", "mutates": False})
        for item in files["compose_files"]:
            commands.append({"purpose": "Validate Compose configuration", "command": f"docker compose -f {item['relative_path']} config", "mutates": False})
        warnings = []
        if not commands:
            warnings.append("No Docker validation commands suggested because no Docker files were found")
        return {"success": True, "project_path": files["project_path"], "commands": commands, "warnings": warnings}
