"""User-run command handoff MCP tools.

Use these tools when an agent should not or cannot perform an action directly
inside a sandbox. They create auditable scripts and command plans for the user
to run manually in their own terminal.
"""

from __future__ import annotations

import re
import textwrap
import time
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


SAFE_SCRIPT_DIR_NAME = "user-run-scripts"


SCRIPT_TEMPLATES = {
    "github_split": {
        "filename": "run-github-split.ps1",
        "risk": "medium",
        "purpose": "Create GitHub-ready Skill-Agents and ai-desk-mcp-tools folders without deleting the combined repo.",
        "body": r"""
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\prepare-github-split.ps1") -Clean:$Clean
""",
    },
    "install_mcp_dependencies": {
        "filename": "run-install-mcp-dependencies.ps1",
        "risk": "medium",
        "purpose": "Create/update the MCP tools virtual environment and install Python dependencies.",
        "body": r"""
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Tools = Join-Path $Root "mcp-tools"
$Venv = Join-Path $Tools ".venv"

if (-not (Test-Path $Venv)) {
    python -m venv $Venv
}

& (Join-Path $Venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $Venv "Scripts\pip.exe") install -r (Join-Path $Tools "requirements.txt")
""",
    },
    "install_playwright": {
        "filename": "run-install-playwright.ps1",
        "risk": "medium",
        "purpose": "Install Playwright browser runtime for local browser/page tools.",
        "body": r"""
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root "mcp-tools\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "MCP tools virtualenv not found. Run run-install-mcp-dependencies.ps1 first."
}

& $Python -m playwright install chromium
""",
    },
    "validate_all": {
        "filename": "run-validate-all.ps1",
        "risk": "low",
        "purpose": "Run all repo validators and MCP tool tests.",
        "body": r"""
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BundledPython = "C:\Users\natth\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path $BundledPython) {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\validate-all.ps1") -Python $BundledPython
}
else {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\validate-all.ps1")
}
""",
    },
    "git_publish_skill_agents": {
        "filename": "run-git-publish-skill-agents.ps1",
        "risk": "high",
        "purpose": "Initialize and push the GitHub-ready Skill-Agents repo. Requires a remote URL.",
        "body": r"""
param(
    [Parameter(Mandatory = $true)][string]$RemoteUrl,
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Repo = Join-Path $Root "github-ready\Skill-Agents"

if (-not (Test-Path $Repo)) {
    throw "Missing $Repo. Run run-github-split.ps1 first."
}

Push-Location $Repo
try {
    if (-not (Test-Path ".git")) {
        git init
    }
    git checkout -B $Branch
    git add .
    git commit -m "Initial Skill-Agents publish"
    git remote remove origin 2>$null
    git remote add origin $RemoteUrl
    git push -u origin $Branch
}
finally {
    Pop-Location
}
""",
    },
    "git_publish_mcp_tools": {
        "filename": "run-git-publish-ai-desk-mcp-tools.ps1",
        "risk": "high",
        "purpose": "Initialize and push the GitHub-ready ai-desk-mcp-tools repo. Requires a remote URL.",
        "body": r"""
param(
    [Parameter(Mandatory = $true)][string]$RemoteUrl,
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Repo = Join-Path $Root "github-ready\ai-desk-mcp-tools"

if (-not (Test-Path $Repo)) {
    throw "Missing $Repo. Run run-github-split.ps1 first."
}

Push-Location $Repo
try {
    if (-not (Test-Path ".git")) {
        git init
    }
    git checkout -B $Branch
    git add .
    git commit -m "Initial ai-desk-mcp-tools publish"
    git remote remove origin 2>$null
    git remote add origin $RemoteUrl
    git push -u origin $Branch
}
finally {
    Pop-Location
}
""",
    },
    "mcp_server_config_hint": {
        "filename": "run-show-mcp-server-config.ps1",
        "risk": "low",
        "purpose": "Print a Claude Desktop-style MCP server config snippet for ai-desk-tools.",
        "body": r"""
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root "mcp-tools\.venv\Scripts\python.exe"
$Server = Join-Path $Root "mcp-tools\server.py"

@"
{
  "mcpServers": {
    "ai-desk-tools": {
      "command": "$Python",
      "args": ["$Server"]
    }
  }
}
"@
""",
    },
}


def _script_dir(project_path: str | None) -> Path:
    root = resolve_allowed_path(project_path or ".", access="write")
    target = root / SAFE_SCRIPT_DIR_NAME
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PolicyError("script_dir_create_failed", str(exc), {"path": str(target)}) from exc
    return target


def _normalize_script_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip())
    if not clean.lower().endswith(".ps1"):
        clean += ".ps1"
    return clean[:120]


def _script_header(title: str, risk: str, purpose: str) -> str:
    return textwrap.dedent(
        f"""\
        # {title}
        # Risk: {risk}
        # Purpose: {purpose}
        # Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
        #
        # Review this script before running it.
        # Run from the combined Skill-Agents repo unless the script says otherwise.

        """
    )


def _write_script(script_dir: Path, filename: str, body: str, title: str, risk: str, purpose: str) -> dict:
    target = script_dir / _normalize_script_name(filename)
    content = _script_header(title, risk, purpose) + textwrap.dedent(body).strip() + "\n"
    command = f"powershell -NoProfile -ExecutionPolicy Bypass -File .\\{SAFE_SCRIPT_DIR_NAME}\\{target.name}"
    try:
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "command": command, "risk": risk, "purpose": purpose, "write_skipped": False}
    except OSError as exc:
        if target.exists():
            return {
                "path": str(target),
                "command": command,
                "risk": risk,
                "purpose": purpose,
                "write_skipped": True,
                "write_warning": str(exc),
            }
        raise


def register(mcp) -> None:
    """Register user-run handoff tools."""

    @mcp.tool()
    def list_user_run_templates() -> dict:
        """List built-in script templates for actions the user should run manually."""
        return {
            "success": True,
            "templates": [
                {"id": key, "filename": value["filename"], "risk": value["risk"], "purpose": value["purpose"]}
                for key, value in SCRIPT_TEMPLATES.items()
            ],
        }

    @mcp.tool()
    def plan_user_run_command(command: str, purpose: str, risk: str = "medium") -> dict:
        """Create a structured handoff plan for a command the user may run manually."""
        risk = risk.lower().strip()
        if risk not in {"low", "medium", "high"}:
            return {"success": False, "error": "invalid_risk", "allowed": ["low", "medium", "high"]}
        warnings = []
        lowered = command.lower()
        if any(token in lowered for token in [" reset --hard", " clean -fd", " remove-item", " rm ", " del "]):
            warnings.append("Command appears destructive. Review carefully before running.")
        if any(token in lowered for token in ["git push", "pip install", "playwright install", "npm install"]):
            warnings.append("Command may use network or change local environment.")
        return {"success": True, "command": command, "purpose": purpose, "risk": risk, "warnings": warnings}

    @mcp.tool()
    def write_user_run_script(script_name: str, body: str, purpose: str, risk: str = "medium", project_path: str | None = None) -> dict:
        """Write a PowerShell script for the user to review and run manually."""
        risk = risk.lower().strip()
        if risk not in {"low", "medium", "high"}:
            return {"success": False, "error": "invalid_risk", "allowed": ["low", "medium", "high"]}
        try:
            out_dir = _script_dir(project_path)
            result = _write_script(out_dir, script_name, body, script_name, risk, purpose)
        except PolicyError as exc:
            audit("user_runner.write_user_run_script", False, {"script_name": script_name, "error": exc.code})
            return policy_error_result(exc)
        audit("user_runner.write_user_run_script", True, {"path": result["path"], "risk": risk})
        return {"success": True, **result}

    @mcp.tool()
    def write_user_run_template(template_id: str, project_path: str | None = None) -> dict:
        """Write one built-in user-run script template."""
        template = SCRIPT_TEMPLATES.get(template_id)
        if not template:
            return {"success": False, "error": "unknown_template", "available": sorted(SCRIPT_TEMPLATES)}
        try:
            out_dir = _script_dir(project_path)
            result = _write_script(out_dir, template["filename"], template["body"], template_id, template["risk"], template["purpose"])
        except PolicyError as exc:
            audit("user_runner.write_user_run_template", False, {"template_id": template_id, "error": exc.code})
            return policy_error_result(exc)
        audit("user_runner.write_user_run_template", True, {"template_id": template_id, "path": result["path"]})
        return {"success": True, "template_id": template_id, **result}

    @mcp.tool()
    def write_all_project_user_run_scripts(project_path: str | None = None) -> dict:
        """Write all built-in user-run scripts for this project."""
        written = []
        for template_id in SCRIPT_TEMPLATES:
            result = write_user_run_template(template_id, project_path)
            written.append(result)
        return {"success": all(item.get("success") for item in written), "count": len(written), "scripts": written}

    @mcp.tool()
    def validate_user_run_script(script_path: str) -> dict:
        """Inspect a generated script for risk hints without executing it."""
        try:
            path = resolve_allowed_path(script_path, access="read")
        except PolicyError as exc:
            return policy_error_result(exc)
        if not path.exists() or not path.is_file():
            return {"success": False, "error": "script_not_found", "path": str(path)}
        text = path.read_text(encoding="utf-8", errors="replace")
        risk_hints = []
        for pattern in ["git push", "pip install", "playwright install", "Remove-Item", "robocopy", "git commit"]:
            if pattern.lower() in text.lower():
                risk_hints.append(pattern)
        return {"success": True, "path": str(path), "line_count": len(text.splitlines()), "risk_hints": risk_hints}
