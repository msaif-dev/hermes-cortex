"""Document Search MCP Server.

Exposes tools for searching documentation, reports, and knowledge base files.
Compliant with MCP 2026-07-28 specification using FastMCP.

Requirements: FR-MCP-001, GEMINI.md §11.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server import MCPServer
from pydantic import Field

from hermes_mcp.logging import get_logger
from hermes_mcp.security.input_validation import validate_tool_output

logger = get_logger(__name__)

mcp = MCPServer(
    "DocumentSearchServer",
    instructions=(
        "Provides document search capabilities over curated analytical reports and guides."
    ),
)

# In-memory document index for standalone and test operation
_SAMPLE_DOCS: list[dict[str, Any]] = [
    {
        "id": "doc-001",
        "title": "Q3 2026 Financial Analysis & Forecast",
        "category": "finance",
        "content": (
            "Operating margins increased by 4.2% across North America. "
            "Cloud infrastructure spend normalized under budget ceilings."
        ),
        "tags": ["finance", "q3", "revenue", "cloud"],
    },
    {
        "id": "doc-002",
        "title": "Enterprise Security Policy - Data Classification",
        "category": "security",
        "content": (
            "Customer PII must be encrypted at rest and in transit. "
            "Read-only service accounts must be used by default for analytical agents."
        ),
        "tags": ["security", "compliance", "policy", "pii"],
    },
    {
        "id": "doc-003",
        "title": "PostgreSQL Warehouse Schema Guide",
        "category": "data_engineering",
        "content": (
            "The sample_data table contains quarterly revenue and expense figures "
            "categorized by department. Use indexed timestamps for partitioning."
        ),
        "tags": ["database", "schema", "postgres", "data_engineering"],
    },
]


@mcp.tool(name="search_docs")
async def search_docs(
    query: Annotated[
        str,
        Field(
            description="Search term or phrase to query the document corpus",
            min_length=1,
            max_length=500,
        ),
    ],
    category: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional category filter (e.g. finance, security, data_engineering)",
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(default=5, ge=1, le=20, description="Maximum number of document excerpts to return"),
    ] = 5,
) -> str:
    """Search the document corpus for relevant analytical reports and documentation.

    Returns matching documents ranked by keyword match and relevance.
    """
    logger.info("searching_docs", query=query, category=category, limit=limit)

    query_lower = query.lower()
    query_terms = set(query_lower.split())

    matches: list[dict[str, Any]] = []
    for doc in _SAMPLE_DOCS:
        if category and doc.get("category", "").lower() != category.lower():
            continue

        content = doc.get("content", "").lower()
        title = doc.get("title", "").lower()
        tags = [t.lower() for t in doc.get("tags", [])]

        score = 0
        for term in query_terms:
            if term in title:
                score += 3
            if term in tags:
                score += 2
            if term in content:
                score += 1

        if score > 0 or query_lower in content:
            matches.append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "category": doc["category"],
                    "score": max(score, 1),
                    "excerpt": doc["content"],
                }
            )

    # Sort by relevance score descending
    matches.sort(key=lambda x: x["score"], reverse=True)
    results = matches[:limit]

    output = json.dumps(
        {"query": query, "total_matches": len(results), "documents": results}, indent=2
    )
    sanitized = validate_tool_output(output)
    return sanitized.sanitized_input


if __name__ == "__main__":
    mcp.run()
