"""Smoke test verifying the official Hermes Agent runtime and MCP connectivity.

Requirements: Acceptance Criteria, ADR-003.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _get_hermes_bin() -> str:
    """Resolve path to hermes CLI binary in the active virtual environment."""
    bin_name = "hermes.exe" if sys.platform == "win32" else "hermes"
    venv_bin = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin") / bin_name
    if venv_bin.is_file():
        return str(venv_bin)
    return shutil.which("hermes") or str(venv_bin)


def test_hermes_cli_version() -> None:
    """Verify hermes CLI binary is installed and reports correct version."""
    hermes_bin = _get_hermes_bin()
    result = subprocess.run(  # noqa: S603
        [hermes_bin, "version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Hermes Agent v0.19.0" in result.stdout
    assert "Install method: pip" in result.stdout


def test_hermes_mcp_servers_registered() -> None:
    """Verify that all 4 platform MCP servers are listed by Hermes Agent."""
    hermes_bin = _get_hermes_bin()
    result = subprocess.run(  # noqa: S603
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
    hermes_bin = _get_hermes_bin()
    result = subprocess.run(  # noqa: S603
        [hermes_bin, "mcp", "test", "document_search"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Connected" in result.stdout
    assert "search_docs" in result.stdout
