"""Code Search MCP Server.

Provides safe repository and codebase searching tools using pattern matching.
Enforces path boundaries to prevent path traversal attacks and secret leakage.

Requirements: FR-MCP-003, GEMINI.md §11, SEC-005.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any

from mcp.server import MCPServer
from pydantic import Field

from hermes_mcp.logging import get_logger
from hermes_mcp.security.input_validation import validate_tool_output

logger = get_logger(__name__)

mcp = MCPServer(
    "CodeSearchServer",
    instructions="Provides safe source code and repository searching tools across project files.",
)

# Files and directories strictly excluded from code search for security
_EXCLUDED_PATTERNS = {
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.cert",
    "*.secret",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

_ALLOWED_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".sql",
    ".txt",
    ".sh",
    ".dockerfile",
    "Dockerfile",
}


def _is_sensitive_path(path: Path) -> bool:
    """Check if a path matches sensitive or secret file patterns."""
    name = path.name.lower()
    if name.startswith(".env"):
        return True
    if name.endswith((".pem", ".key", ".cert", ".p12", ".pfx")):
        return True
    parts = set(path.parts)
    return bool(parts.intersection({".git", ".venv", "__pycache__"}))


MAX_SNIPPETS_PER_FILE: int = 5


def _search_single_file(
    file_path: Path,
    root_dir: Path,
    term: str,
    compiled: re.Pattern[str] | None,
) -> dict[str, Any] | None:
    """Scan a single file for occurrences of term or regex pattern."""
    if not file_path.is_file() or _is_sensitive_path(file_path):
        return None
    if (
        file_path.suffix.lower() not in _ALLOWED_EXTENSIONS
        and file_path.name not in _ALLOWED_EXTENSIONS
    ):
        return None

    try:
        rel_path = file_path.relative_to(root_dir).as_posix()
        content = file_path.read_text(encoding="utf-8", errors="replace")

        matching_lines: list[dict[str, Any]] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            matched = bool(compiled.search(line)) if compiled else (term.lower() in line.lower())
            if matched:
                matching_lines.append(
                    {
                        "line_number": line_no,
                        "content": line.strip()[:200],
                    }
                )
                if len(matching_lines) >= MAX_SNIPPETS_PER_FILE:
                    break

        if matching_lines:
            return {
                "file": rel_path,
                "matches_found": len(matching_lines),
                "snippets": matching_lines,
            }
    except Exception as e:
        logger.debug("file_search_read_error", file=str(file_path), error=str(e))

    return None


@mcp.tool(name="search_code")
async def search_code(
    term: Annotated[
        str,
        Field(
            description="Search string or regex pattern to look for in code",
            min_length=1,
            max_length=200,
        ),
    ],
    search_path: Annotated[
        str, Field(default=".", description="Relative subfolder within the workspace to search")
    ] = ".",
    is_regex: Annotated[
        bool, Field(default=False, description="Whether to treat term as a regular expression")
    ] = False,
    max_results: Annotated[
        int,
        Field(default=10, ge=1, le=50, description="Maximum number of file matches to return"),
    ] = 10,
) -> str:
    """Search project source code files for a given term or regular expression.

    Guarantees isolation: rejects directory traversal ('../') and protects secrets.
    """
    logger.info("searching_code", term=term, search_path=search_path, is_regex=is_regex)

    normalized_path = Path(search_path)
    if ".." in normalized_path.parts:
        return json.dumps(
            {
                "error": "PATH_TRAVERSAL_DETECTED",
                "message": "Access outside the workspace root is prohibited.",
            },
            indent=2,
        )

    root_dir = Path.cwd().resolve()
    target_dir = (root_dir / normalized_path).resolve()

    try:
        target_dir.relative_to(root_dir)
    except ValueError:
        return json.dumps(
            {
                "error": "PATH_TRAVERSAL_DETECTED",
                "message": "Target directory is outside repository root.",
            },
            indent=2,
        )

    if not target_dir.exists():
        return json.dumps(
            {
                "error": "DIRECTORY_NOT_FOUND",
                "message": f"Directory '{search_path}' does not exist.",
            },
            indent=2,
        )

    compiled: re.Pattern[str] | None = None
    if is_regex:
        try:
            compiled = re.compile(term, re.IGNORECASE)
        except re.error as e:
            return json.dumps(
                {
                    "error": "INVALID_REGEX",
                    "message": f"Regular expression error: {e!s}",
                },
                indent=2,
            )

    matches: list[dict[str, Any]] = []
    for file_path in target_dir.rglob("*"):
        match_result = _search_single_file(file_path, root_dir, term, compiled)
        if match_result:
            matches.append(match_result)
            if len(matches) >= max_results:
                break

    output = json.dumps(
        {
            "term": term,
            "is_regex": is_regex,
            "total_files_matched": len(matches),
            "results": matches,
        },
        indent=2,
    )

    return validate_tool_output(output).sanitized_input


if __name__ == "__main__":
    mcp.run()
