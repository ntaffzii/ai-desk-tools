"""Register all MCP tool groups."""

from tools import api, audit, backup, browser, browser_page_map, calendar, ci, code_editing, config, database, dependency_risk, docker, docs, email_inbox, external_mcp_catalog, figma, finance_market, filesystem, git, git_control, github, github_api, issue_tracker, mcp_security_audit, media, memory, memory_context, notion, obsidian_notion_bridge, package, playwright_actions, playwright_tools, postgres, project, prompt_improver, rag_adapter, registry, release, repo_index, sandbox, security_scanner, skill_runtime, slack_discord, structured_data, system, task, test_inspection, toolsets, user_runner, validation, vector_memory, web, web_capture


TOOL_GROUPS = (
    filesystem,
    registry,
    skill_runtime,
    toolsets,
    audit,
    mcp_security_audit,
    security_scanner,
    project,
    docs,
    repo_index,
    external_mcp_catalog,
    package,
    docker,
    api,
    database,
    config,
    test_inspection,
    ci,
    task,
    dependency_risk,
    release,
    backup,
    structured_data,
    memory,
    memory_context,
    vector_memory,
    rag_adapter,
    finance_market,
    notion,
    obsidian_notion_bridge,
    calendar,
    email_inbox,
    figma,
    slack_discord,
    issue_tracker,
    github,
    github_api,
    browser,
    browser_page_map,
    sandbox,
    git,
    git_control,
    playwright_tools,
    playwright_actions,
    code_editing,
    postgres,
    user_runner,
    validation,
    prompt_improver,
    web,
    web_capture,
    media,
    system,
)

import os
import json
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent.parent  # mcp-tools
REPO_ROOT = TOOLS_ROOT.parent                       # repo root
CONFIG_PATH = TOOLS_ROOT / "config" / "active_config.json"
TOOLSETS_PATH = REPO_ROOT / "data" / "toolsets.json"

MODULE_MAP = {
    "filesystem": filesystem,
    "registry": registry,
    "skill-runtime": skill_runtime,
    "toolsets": toolsets,
    "audit": audit,
    "mcp-security-audit": mcp_security_audit,
    "security-scanner": security_scanner,
    "project": project,
    "docs": docs,
    "repo-index": repo_index,
    "external-mcp-catalog": external_mcp_catalog,
    "package": package,
    "docker": docker,
    "api": api,
    "database": database,
    "config": config,
    "test-inspection": test_inspection,
    "ci": ci,
    "task": task,
    "dependency-risk": dependency_risk,
    "release": release,
    "backup": backup,
    "structured-data": structured_data,
    "memory": memory,
    "memory-context": memory_context,
    "vector-memory": vector_memory,
    "rag-adapter": rag_adapter,
    "finance-market": finance_market,
    "notion": notion,
    "obsidian-notion-bridge": obsidian_notion_bridge,
    "calendar": calendar,
    "email-inbox": email_inbox,
    "figma": figma,
    "slack-discord": slack_discord,
    "issue-tracker": issue_tracker,
    "github": github,
    "github-api": github_api,
    "browser": browser,
    "browser-page-map": browser_page_map,
    "sandbox": sandbox,
    "git": git,
    "git-control": git_control,
    "playwright": playwright_tools,
    "playwright-actions": playwright_actions,
    "code-editing": code_editing,
    "postgres": postgres,
    "user-runner": user_runner,
    "validation": validation,
    "prompt-improver": prompt_improver,
    "web": web,
    "web-capture": web_capture,
    "media": media,
    "system": system,
}


def _load_active_config() -> dict | None:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error reading active_config.json: {e}")
    return None


def _get_groups_for_toolset(toolset_id: str) -> set[str]:
    groups = set()
    try:
        if TOOLSETS_PATH.exists():
            with open(TOOLSETS_PATH, "r", encoding="utf-8") as f:
                toolsets_data = json.load(f)
            for ts in toolsets_data:
                if ts.get("id") == toolset_id:
                    groups.update(ts.get("toolGroups", []))
                    break
    except Exception as e:
        print(f"Error reading toolsets.json: {e}")
    return groups


def register_all_tools(mcp) -> None:
    """Register tool modules dynamically based on env vars or active_config.json."""
    core_groups = {"registry", "toolsets", "skill-runtime"}
    
    # Check env variables first (highest priority)
    toolset_id = os.getenv("MCP_TOOLSET")
    groups_env = os.getenv("MCP_TOOL_GROUPS")
    
    selected_groups = set()
    
    if groups_env:
        for g in groups_env.split(","):
            g = g.strip()
            if g:
                selected_groups.add(g)
    elif toolset_id:
        selected_groups = _get_groups_for_toolset(toolset_id)
    else:
        # Check active_config.json
        config_data = _load_active_config()
        if config_data:
            ts_id = config_data.get("active_toolset")
            grps = config_data.get("active_groups", [])
            if ts_id:
                selected_groups = _get_groups_for_toolset(ts_id)
            elif grps:
                selected_groups = set(grps)
                
    if selected_groups:
        selected_groups.update(core_groups)
        modules_to_register = []
        for g in selected_groups:
            if g in MODULE_MAP:
                modules_to_register.append(MODULE_MAP[g])
            else:
                print(f"Warning: Tool group '{g}' not found in MODULE_MAP.")
        
        modules_to_register = [m for m in TOOL_GROUPS if m in modules_to_register]
    else:
        modules_to_register = list(TOOL_GROUPS)
        
    for module in modules_to_register:
        module.register(mcp)

