"""Smoke test verifying the official Hermes Agent runtime and MCP connectivity.

Requirements: Acceptance Criteria, ADR-003.
"""
from __future__ import annotations

import shutil
import subprocess
import sys


def test_hermes_cli_version() -> None:
    """Verify hermes CLI binary is installed and reports correct version."""
    hermes_bin = shutil.which("hermes") or (
        sys.prefix + "\\Scripts\\hermes.exe" if sys.platform == "win32" else sys.prefix + "/bin/hermes"
    )
    result = subprocess.run(
        [hermes_bin, "version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Hermes Agent v0.19.0" in result.stdout
    assert "Install method: pip" in result.stdout


def test_hermes_mcp_servers_registered() -> None:
    """Verify that all 4 platform MCP servers are listed by Hermes Agent."""
    hermes_bin = shutil.which("hermes") or (
        sys.prefix + "\\Scripts\\hermes.exe" if sys.platform == "win32" else sys.prefix + "/bin/hermes"
    )
    result = subprocess.run(
        [hermes_bin, "mcp", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.lower()
    assert "document_search" in output
    assert "postgres_query" in output
    assert "code_search" in output
    assert "execution_sandbox" in output


def test_hermes_mcp_document_search_connection() -> None:
    """Verify that Hermes Agent successfully connects to document_search MCP server."""
    hermes_bin = shutil.which("hermes") or (
        sys.prefix + "\\Scripts\\hermes.exe" if sys.platform == "win32" else sys.prefix + "/bin/hermes"
    )
    result = subprocess.run(
        [hermes_bin, "mcp", "test", "document_search"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Connected" in result.stdout
    assert "search_docs" in result.stdout
