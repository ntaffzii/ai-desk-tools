"""Postgres read-only planning and query tools."""

from __future__ import annotations

import os
import re


READONLY_RE = re.compile(r"^\s*(select|with|explain)\b", re.I)
MUTATING_RE = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call)\b", re.I)


def _dsn() -> str:
    return os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or ""


def _redact(value: str) -> str:
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", value)


def register(mcp) -> None:
    """Register Postgres tools."""

    @mcp.tool()
    def check_postgres_config() -> dict:
        """Check whether a Postgres DSN is configured."""
        dsn = _dsn()
        return {"success": True, "configured": bool(dsn), "dsn_redacted": _redact(dsn) if dsn else "", "env_keys": [key for key in ["POSTGRES_DSN", "DATABASE_URL"] if os.getenv(key)]}

    @mcp.tool()
    def explain_sql_risk(sql: str) -> dict:
        """Classify SQL as read-only or risky."""
        readonly = bool(READONLY_RE.search(sql)) and not MUTATING_RE.search(sql)
        risk = "low" if readonly else "high"
        warnings = [] if readonly else ["Only SELECT/WITH/EXPLAIN queries are allowed by this tool."]
        return {"success": True, "readonly": readonly, "risk": risk, "warnings": warnings}

    @mcp.tool()
    def plan_readonly_query(sql: str, max_rows: int = 100) -> dict:
        """Plan a read-only SQL query without executing it."""
        risk = explain_sql_risk(sql)
        safe_limit = max(1, min(int(max_rows), 1000))
        limited_sql = sql.strip().rstrip(";")
        if risk["readonly"] and not re.search(r"\blimit\s+\d+\b", limited_sql, re.I):
            limited_sql = f"{limited_sql} LIMIT {safe_limit}"
        return {"success": True, "sql": sql, "planned_sql": limited_sql, "max_rows": safe_limit, "risk": risk}

    @mcp.tool()
    def run_readonly_sql(sql: str, max_rows: int = 100) -> dict:
        """Run a read-only SQL query when psycopg and DSN are configured."""
        plan = plan_readonly_query(sql, max_rows)
        if not plan["risk"]["readonly"]:
            return {"success": False, "error": "sql_not_readonly", "risk": plan["risk"]}
        dsn = _dsn()
        if not dsn:
            return {"success": False, "error": "postgres_dsn_missing", "message": "Set POSTGRES_DSN or DATABASE_URL."}
        try:
            import psycopg
        except ImportError:
            return {"success": False, "error": "psycopg_not_installed"}
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(plan["planned_sql"])
                    columns = [desc[0] for desc in cur.description or []]
                    rows = cur.fetchmany(max(1, min(int(max_rows), 1000)))
            return {"success": True, "columns": columns, "rows": rows, "row_count": len(rows), "planned_sql": plan["planned_sql"]}
        except Exception as exc:
            return {"success": False, "error": "query_failed", "message": str(exc)}

    @mcp.tool()
    def inspect_query_result(columns_json: str, rows_json: str) -> dict:
        """Inspect a supplied query result shape."""
        import json

        try:
            columns = json.loads(columns_json)
            rows = json.loads(rows_json)
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_json", "message": str(exc)}
        return {"success": True, "column_count": len(columns), "row_count": len(rows), "columns": columns, "sample_rows": rows[:5]}
