"""Optional GitHub API MCP tools."""

from __future__ import annotations

import os
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

try:
    import requests
except ModuleNotFoundError:
    requests = None

from security import audit


GITHUB_API = "https://api.github.com"


def _token() -> str:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or ""


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_get(path: str, params: dict | None = None) -> dict:
    if not _token():
        return {"success": False, "error": "github_token_missing", "message": "Set GITHUB_TOKEN or GH_TOKEN to use GitHub API tools."}
    url = f"{GITHUB_API}{path}"
    if requests is not None:
        response = requests.get(url, headers=_headers(), params=params or {}, timeout=20)
        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text[:2000]}
        return {"success": 200 <= response.status_code < 300, "status_code": response.status_code, "url": url, "data": data}

    query = urlencode(params or {})
    request_url = f"{url}?{query}" if query else url
    request = Request(request_url, headers=_headers())
    with urlopen(request, timeout=20) as response:
        raw = response.read(2_000_000).decode("utf-8", errors="replace")
        try:
            import json

            data = json.loads(raw)
        except ValueError:
            data = {"text": raw[:2000]}
        status_code = response.getcode()
    return {"success": 200 <= status_code < 300, "status_code": status_code, "url": url, "data": data}


def _repo_path(owner: str, repo: str) -> str:
    return f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"


def register(mcp) -> None:
    """Register GitHub API tools."""

    @mcp.tool()
    def check_github_api_auth() -> dict:
        """Check whether GitHub API token environment variables are present."""
        present = [key for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN") if os.getenv(key)]
        return {"success": True, "token_present": bool(present), "token_env_keys_present": present}

    @mcp.tool()
    def get_repo_info(owner: str, repo: str) -> dict:
        """Get GitHub repository metadata."""
        result = _github_get(_repo_path(owner, repo))
        audit("github_api.get_repo_info", result.get("success", False), {"owner": owner, "repo": repo, "status_code": result.get("status_code")})
        return result

    @mcp.tool()
    def get_issue(owner: str, repo: str, issue_number: int) -> dict:
        """Get one GitHub issue."""
        result = _github_get(f"{_repo_path(owner, repo)}/issues/{int(issue_number)}")
        audit("github_api.get_issue", result.get("success", False), {"owner": owner, "repo": repo, "issue_number": issue_number})
        return result

    @mcp.tool()
    def get_pull_request(owner: str, repo: str, pull_number: int) -> dict:
        """Get one GitHub pull request."""
        result = _github_get(f"{_repo_path(owner, repo)}/pulls/{int(pull_number)}")
        audit("github_api.get_pull_request", result.get("success", False), {"owner": owner, "repo": repo, "pull_number": pull_number})
        return result

    @mcp.tool()
    def list_pr_files(owner: str, repo: str, pull_number: int) -> dict:
        """List files changed in a GitHub pull request."""
        result = _github_get(f"{_repo_path(owner, repo)}/pulls/{int(pull_number)}/files", {"per_page": 100})
        audit("github_api.list_pr_files", result.get("success", False), {"owner": owner, "repo": repo, "pull_number": pull_number})
        return result

    @mcp.tool()
    def get_pr_checks(owner: str, repo: str, ref: str) -> dict:
        """Get check runs for a branch, tag, or commit SHA."""
        result = _github_get(f"{_repo_path(owner, repo)}/commits/{quote(ref, safe='')}/check-runs")
        audit("github_api.get_pr_checks", result.get("success", False), {"owner": owner, "repo": repo, "ref": ref})
        return result

    @mcp.tool()
    def draft_pr_review(summary: str, findings: str = "", tests: str = "", recommendation: str = "comment") -> dict:
        """Draft a PR review body without submitting it."""
        body = f"## Summary\n\n{summary.strip()}\n\n## Findings\n\n{findings.strip() or 'No findings listed.'}\n\n## Tests\n\n{tests.strip() or 'Not run.'}\n\n## Recommendation\n\n{recommendation.strip()}\n"
        return {"success": True, "body": body}
