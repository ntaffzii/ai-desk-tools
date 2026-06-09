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


def register_all_tools(mcp) -> None:
    """Register every tool module with a FastMCP server instance."""
    for module in TOOL_GROUPS:
        module.register(mcp)
