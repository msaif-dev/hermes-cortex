"""Unit tests for MCP tool servers.

Tests document search, postgres query validation, code search isolation,
and sandbox execution.

Requirements: FR-MCP-001 through FR-MCP-004, SEC-003 through SEC-006.
"""

from __future__ import annotations

import json

from hermes_mcp.mcp_servers.code_search import search_code
from hermes_mcp.mcp_servers.document_search import search_docs
from hermes_mcp.mcp_servers.execution_sandbox import run_python
from hermes_mcp.mcp_servers.postgres_query import list_tables, run_sql


class TestDocumentSearchServer:
    """Tests for document search tool."""

    async def test_search_docs_returns_matches(self) -> None:
        raw_result = await search_docs(query="revenue")
        data = json.loads(raw_result)
        assert "documents" in data
        assert data["total_matches"] > 0
        assert any(
            "revenue" in doc["title"].lower() or "revenue" in doc["excerpt"].lower()
            for doc in data["documents"]
        )

    async def test_search_docs_with_category_filter(self) -> None:
        raw_result = await search_docs(query="security", category="security")
        data = json.loads(raw_result)
        assert data["total_matches"] > 0
        for doc in data["documents"]:
            assert doc["category"] == "security"

    async def test_search_docs_no_match(self) -> None:
        raw_result = await search_docs(query="nonexistent_xyz_term_12345")
        data = json.loads(raw_result)
        assert data["total_matches"] == 0
        assert data["documents"] == []

    async def test_search_docs_workspace_indexing(self) -> None:
        raw_result = await search_docs(query="architecture")
        data = json.loads(raw_result)
        assert data["total_matches"] > 0
        assert any("architecture" in doc["title"].lower() for doc in data["documents"])


class TestPostgresQueryServer:
    """Tests for PostgreSQL query tool."""

    async def test_run_sql_safe_select_query(self) -> None:
        raw_result = await run_sql(query="SELECT * FROM sample_data LIMIT 5")
        data = json.loads(raw_result)
        # Should either execute or return valid offline simulated schema
        assert "error" not in data or data.get("error") != "SQL_VALIDATION_ERROR"
        assert "query" in data

    async def test_run_sql_blocks_destructive_query(self) -> None:
        raw_result = await run_sql(query="DROP TABLE sample_data")
        data = json.loads(raw_result)
        assert data.get("error") == "SQL_VALIDATION_ERROR"
        assert "violations" in data

    async def test_run_sql_blocks_insert_mutation(self) -> None:
        raw_result = await run_sql(query="INSERT INTO sample_data (category) VALUES ('hack')")
        data = json.loads(raw_result)
        assert data.get("error") == "SQL_VALIDATION_ERROR"

    async def test_list_tables(self) -> None:
        raw_result = await list_tables()
        data = json.loads(raw_result)
        assert "error" not in data or data.get("error") != "SQL_VALIDATION_ERROR"


class TestCodeSearchServer:
    """Tests for code search tool."""

    async def test_search_code_finds_matches(self) -> None:
        raw_result = await search_code(term="FastMCP", search_path="src")
        data = json.loads(raw_result)
        assert "results" in data
        assert data["total_files_matched"] > 0
        assert any("mcp_servers" in r["file"] for r in data["results"])

    async def test_search_code_blocks_path_traversal(self) -> None:
        raw_result = await search_code(term="password", search_path="../../..")
        data = json.loads(raw_result)
        assert data.get("error") == "PATH_TRAVERSAL_DETECTED"

    async def test_search_code_invalid_regex(self) -> None:
        raw_result = await search_code(term="[unclosed_bracket", is_regex=True)
        data = json.loads(raw_result)
        assert data.get("error") == "INVALID_REGEX"


class TestExecutionSandboxServer:
    """Tests for execution sandbox tool."""

    async def test_run_python_simple_computation(self) -> None:
        code = "print(10 + 25)"
        raw_result = await run_python(code=code, timeout_s=10)
        data = json.loads(raw_result)
        assert data["exit_code"] == 0
        assert "35" in data["stdout"]
        assert data["sandboxed"] is True

    async def test_run_python_syntax_error(self) -> None:
        code = "def invalid_syntax("
        raw_result = await run_python(code=code, timeout_s=10)
        data = json.loads(raw_result)
        assert data["exit_code"] != 0
        assert "SyntaxError" in data["stderr"]

    async def test_run_python_blocks_forbidden_local_calls(self) -> None:
        code = "import shutil\nshutil.rmtree('/tmp')"
        raw_result = await run_python(code=code, timeout_s=10)
        data = json.loads(raw_result)
        assert "SECURITY_ERROR" in data["stderr"]
        assert data["exit_code"] == 1

    async def test_run_python_timeout(self) -> None:
        code = "import time\ntime.sleep(5)"
        raw_result = await run_python(code=code, timeout_s=1)
        data = json.loads(raw_result)
        assert "TIMEOUT" in data["stderr"]
        assert data["exit_code"] == -1
