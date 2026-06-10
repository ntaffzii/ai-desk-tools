"""Skill and workflow runtime routing tools for local agents."""

from __future__ import annotations

import json
import re
from pathlib import Path

from security import REPO_ROOT, audit


SKILL_ROOTS = [REPO_ROOT / "skills", REPO_ROOT / "Skill.md"]
WORKFLOWS_REGISTRY = REPO_ROOT / "data" / "workflows.json"
TOOLSETS_REGISTRY = REPO_ROOT / "data" / "toolsets.json"
MAX_CONTEXT_CHARS = 24_000


def _read_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_ก-๙-]+", text) if len(token) >= 2}


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip()


def _skill_files() -> list[Path]:
    files: list[Path] = []
    for root in SKILL_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("SKILL.md")))
    return files


def _skill_index() -> list[dict]:
    skills = []
    for path in _skill_files():
        content = path.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(content)
        name = meta.get("name") or path.parent.name
        description = meta.get("description", "")
        skills.append(
            {
                "name": name,
                "description": description,
                "path": str(path.relative_to(REPO_ROOT)),
                "category": str(path.relative_to(REPO_ROOT).parts[0]),
                "body_chars": len(body),
            }
        )
    return skills


def _score(query: str, haystack: str, exact_bonus: int = 5) -> int:
    query_tokens = _tokens(query)
    hay_tokens = _tokens(haystack)
    if not query_tokens or not hay_tokens:
        return 0
    score = len(query_tokens & hay_tokens)
    lowered_query = query.lower()
    lowered_haystack = haystack.lower()
    for token in query_tokens:
        if token in lowered_haystack and token in lowered_query:
            score += 1
    if lowered_haystack and any(part in lowered_query for part in lowered_haystack.split()[:2]):
        score += exact_bonus
    return score


def _recommend_workflows(task: str, limit: int) -> list[dict]:
    recommendations = []
    for workflow in _read_json(WORKFLOWS_REGISTRY):
        haystack = " ".join(
            [
                workflow.get("id", ""),
                workflow.get("title", ""),
                workflow.get("description", ""),
                " ".join(workflow.get("recommendedSkills", [])),
            ]
        )
        score = _score(task, haystack)
        if score:
            recommendations.append({**workflow, "score": score})
    recommendations.sort(key=lambda item: (-item["score"], item.get("id", "")))
    return recommendations[: max(1, min(int(limit), 10))]


def _recommend_skills(task: str, workflow_ids: list[str], limit: int) -> list[dict]:
    workflow_skill_hints = set()
    for workflow in _read_json(WORKFLOWS_REGISTRY):
        if workflow.get("id") in workflow_ids:
            workflow_skill_hints.update(workflow.get("recommendedSkills", []))
            for step in workflow.get("steps", []):
                workflow_skill_hints.update(step.get("recommendedSkills", []))

    recommendations = []
    for skill in _skill_index():
        haystack = " ".join([skill["name"], skill["description"], skill["path"]])
        score = _score(task, haystack)
        if skill["name"] in workflow_skill_hints:
            score += 6
        if score:
            recommendations.append({**skill, "score": score})
    recommendations.sort(key=lambda item: (-item["score"], item.get("name", "")))
    return recommendations[: max(1, min(int(limit), 12))]


def _recommend_toolsets(task: str, workflow_ids: list[str], limit: int) -> list[dict]:
    workflow_set = set(workflow_ids)
    primary_workflow = workflow_ids[0] if workflow_ids else ""
    recommendations = []
    for toolset in _read_json(TOOLSETS_REGISTRY):
        haystack = " ".join([toolset.get("id", ""), toolset.get("title", ""), toolset.get("description", ""), " ".join(toolset.get("toolGroups", []))])
        score = _score(task, haystack)
        recommended_workflows = set(toolset.get("recommendedWorkflows", []))
        if primary_workflow and primary_workflow in recommended_workflows:
            score += 12
        elif workflow_set & recommended_workflows:
            score += 4
        if score:
            recommendations.append({**toolset, "score": score})
    recommendations.sort(key=lambda item: (-item["score"], item.get("id", "")))
    return recommendations[: max(1, min(int(limit), 8))]


def _load_text(relative_path: str, max_chars: int) -> dict:
    path = (REPO_ROOT / relative_path).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        return {"success": False, "error": "path_outside_repo", "path": relative_path}
    if not path.exists() or path.is_dir():
        return {"success": False, "error": "path_not_found", "path": relative_path}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"success": True, "path": str(path.relative_to(REPO_ROOT)), "content": text[:max_chars], "truncated": len(text) > max_chars}


def register(mcp) -> None:
    """Register skill runtime tools."""

    @mcp.tool()
    def build_skill_index() -> dict:
        """Build an index of available skills from frontmatter only."""
        skills = _skill_index()
        audit("skill_runtime.build_skill_index", True, {"count": len(skills)})
        return {"success": True, "count": len(skills), "skills": skills}

    @mcp.tool()
    def recommend_workflows(task_description: str, limit: int = 5) -> dict:
        """Recommend workflows for a task without loading workflow bodies."""
        items = _recommend_workflows(task_description, limit)
        audit("skill_runtime.recommend_workflows", True, {"count": len(items)})
        return {
            "success": True,
            "count": len(items),
            "recommendations": [
                {"id": item.get("id"), "title": item.get("title"), "description": item.get("description"), "path": item.get("path"), "recommendedSkills": item.get("recommendedSkills", []), "score": item.get("score")}
                for item in items
            ],
        }

    @mcp.tool()
    def recommend_skills(task_description: str, workflow_ids_csv: str = "", limit: int = 8) -> dict:
        """Recommend skills from task text and optional workflow ids."""
        workflow_ids = [item.strip() for item in workflow_ids_csv.split(",") if item.strip()]
        items = _recommend_skills(task_description, workflow_ids, limit)
        audit("skill_runtime.recommend_skills", True, {"count": len(items)})
        return {"success": True, "count": len(items), "recommendations": items}

    @mcp.tool()
    def load_skill(skill_name: str, max_chars: int = 8000) -> dict:
        """Load one skill body by skill name."""
        for skill in _skill_index():
            if skill["name"] == skill_name:
                result = _load_text(skill["path"], max(1000, min(int(max_chars), 20_000)))
                audit("skill_runtime.load_skill", result.get("success", False), {"skill_name": skill_name})
                return result | {"skill": skill}
        audit("skill_runtime.load_skill", False, {"skill_name": skill_name, "error": "skill_not_found"})
        return {"success": False, "error": "skill_not_found", "skill_name": skill_name}

    @mcp.tool()
    def load_workflow(workflow_id: str, max_chars: int = 8000) -> dict:
        """Load one workflow body by workflow id."""
        for workflow in _read_json(WORKFLOWS_REGISTRY):
            if workflow.get("id") == workflow_id:
                result = _load_text(workflow.get("path", ""), max(1000, min(int(max_chars), 20_000)))
                audit("skill_runtime.load_workflow", result.get("success", False), {"workflow_id": workflow_id})
                return result | {"workflow": workflow}
        audit("skill_runtime.load_workflow", False, {"workflow_id": workflow_id, "error": "workflow_not_found"})
        return {"success": False, "error": "workflow_not_found", "workflow_id": workflow_id}

    @mcp.tool()
    def route_request(task_description: str, max_skills: int = 5, max_workflows: int = 3, max_toolsets: int = 3) -> dict:
        """Route a user request to workflows, skills, and toolsets."""
        workflows = _recommend_workflows(task_description, max_workflows)
        workflow_ids = [item.get("id", "") for item in workflows]
        skills = _recommend_skills(task_description, workflow_ids, max_skills)
        toolsets = _recommend_toolsets(task_description, workflow_ids, max_toolsets)
        needs_prompt_improver = len(_tokens(task_description)) < 4 or not workflows and not skills
        result = {
            "success": True,
            "task": task_description,
            "needs_prompt_improver": needs_prompt_improver,
            "workflows": [{"id": item.get("id"), "title": item.get("title"), "path": item.get("path"), "score": item.get("score")} for item in workflows],
            "skills": [{"name": item.get("name"), "path": item.get("path"), "description": item.get("description"), "score": item.get("score")} for item in skills],
            "toolsets": [{"id": item.get("id"), "title": item.get("title"), "toolGroups": item.get("toolGroups", []), "score": item.get("score")} for item in toolsets],
            "next_steps": [
                "If needs_prompt_improver is true, clarify or improve the prompt before execution.",
                "Load only the recommended workflow and skill files needed for the job.",
                "Use the recommended toolset before selecting individual tools.",
                "Prefer read-only or draft-only tools for private data.",
            ],
        }
        audit("skill_runtime.route_request", True, {"workflow_count": len(workflows), "skill_count": len(skills), "toolset_count": len(toolsets)})
        return result

    @mcp.tool()
    def build_agent_context(task_description: str, max_chars: int = MAX_CONTEXT_CHARS) -> dict:
        """Build a compact context pack with selected workflow and skill bodies."""
        route = route_request(task_description)
        budget = max(4000, min(int(max_chars), 60_000))
        chunks = []
        used = 0

        for workflow in route.get("workflows", [])[:2]:
            loaded = load_workflow(workflow["id"], 7000)
            if loaded.get("success"):
                text = f"# Workflow: {workflow['id']}\n\n{loaded['content']}\n"
                if used + len(text) <= budget:
                    chunks.append(text)
                    used += len(text)

        for skill in route.get("skills", [])[:5]:
            loaded = load_skill(skill["name"], 7000)
            if loaded.get("success"):
                text = f"# Skill: {skill['name']}\n\n{loaded['content']}\n"
                if used + len(text) <= budget:
                    chunks.append(text)
                    used += len(text)

        context = "\n\n".join(chunks)
        audit("skill_runtime.build_agent_context", True, {"chars": len(context)})
        return {"success": True, "route": route, "context": context, "chars": len(context), "truncated_by_budget": used >= budget}
