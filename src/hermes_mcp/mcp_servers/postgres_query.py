"""PostgreSQL Query MCP Server.

Provides safe, read-only SQL query tools for analytics.
Enforces strict SQL validation, read-only privilege boundaries,
statement timeouts, and result row ceilings.

Requirements: FR-MCP-002, GEMINI.md §12, SEC-004.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import asyncpg
from mcp.server import MCPServer
from pydantic import Field

from hermes_mcp.config import DatabaseConfig
from hermes_mcp.logging import get_logger
from hermes_mcp.security.input_validation import validate_sql_query, validate_tool_output

logger = get_logger(__name__)

mcp = MCPServer(
    "PostgresQueryServer",
    instructions=(
        "Executes verified read-only analytical SQL queries against the PostgreSQL data warehouse."
    ),
)


class _PoolHolder:
    pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool | None:
    """Acquire or create the asyncpg connection pool."""
    if _PoolHolder.pool is not None:
        loop = getattr(_PoolHolder.pool, "_loop", None)
        if loop is not None and loop.is_closed():
            _PoolHolder.pool = None

    if _PoolHolder.pool is None:
        try:
            config = DatabaseConfig()
            if not config.password.get_secret_value():
                logger.warning("db_password_not_configured")
                return None
            _PoolHolder.pool = await asyncpg.create_pool(
                dsn=config.dsn,
                min_size=config.min_connections,
                max_size=config.max_connections,
                command_timeout=config.statement_timeout_ms / 1000.0,
                timeout=1.0,
            )
        except Exception as e:
            logger.warning("db_connection_pool_failed", error=str(e))
            return None
    return _PoolHolder.pool


@mcp.tool(name="run_sql")
async def run_sql(
    query: Annotated[
        str,
        Field(
            description="Read-only SQL SELECT or WITH query to execute against the warehouse",
            min_length=5,
            max_length=10000,
        ),
    ],
    max_rows: Annotated[
        int, Field(default=100, ge=1, le=1000, description="Maximum number of rows to return")
    ] = 100,
) -> str:
    """Execute a safe, read-only SQL query against the data warehouse.

    Only SELECT, WITH (CTE), and EXPLAIN statements are permitted.
    Mutations (INSERT/UPDATE/DELETE/DROP/ALTER) are strictly blocked.
    """
    logger.info("validating_sql_query", max_rows=max_rows)

    # 1. Deterministic Security Validation
    val = validate_sql_query(query)
    if not val.is_valid:
        logger.warning("sql_query_rejected_by_validator", violations=val.violations)
        return json.dumps(
            {
                "error": "SQL_VALIDATION_ERROR",
                "message": "Query was rejected due to security policy.",
                "violations": val.violations,
            },
            indent=2,
        )

    # 2. Database Connection & Execution
    pool = await get_db_pool()
    if pool is None:
        # Graceful handling when running standalone without live postgres
        return json.dumps(
            {
                "status": "OFFLINE_MODE",
                "message": (
                    "Database connection not available. "
                    "Verified that SQL query is syntactically safe and read-only."
                ),
                "query": val.sanitized_input,
                "simulated_schema": {
                    "columns": ["id", "category", "description", "value", "created_at"],
                    "row_count": 0,
                    "rows": [],
                },
            },
            indent=2,
        )

    try:
        async with pool.acquire() as conn:
            # Set per-statement timeout
            stmt = (
                f"{val.sanitized_input} LIMIT {max_rows}"
                if "LIMIT" not in val.sanitized_input.upper()
                else val.sanitized_input
            )
            records = await conn.fetch(stmt)
            rows = [dict(record) for record in records[:max_rows]]

            # Convert non-serializable objects (like Decimal, datetime)
            def _serialize(obj: Any) -> Any:
                if hasattr(obj, "isoformat"):
                    return obj.isoformat()
                if hasattr(obj, "__str__"):
                    return str(obj)
                return obj

            cleaned_rows = [{k: _serialize(v) for k, v in row.items()} for row in rows]

            output = json.dumps(
                {
                    "query": stmt,
                    "row_count": len(cleaned_rows),
                    "rows": cleaned_rows,
                },
                indent=2,
            )
            return validate_tool_output(output).sanitized_input

    except Exception as e:
        logger.exception("sql_execution_failed", error=str(e), query=val.sanitized_input)
        return json.dumps(
            {
                "error": "EXECUTION_ERROR",
                "message": f"Database execution error: {e!s}",
            },
            indent=2,
        )


@mcp.tool(name="list_tables")
async def list_tables() -> str:
    """List all available public tables in the data warehouse schema."""
    logger.info("fetching_public_table_catalog")

    query = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    res: str = await run_sql(query=query, max_rows=100)
    return res


if __name__ == "__main__":
    mcp.run()
