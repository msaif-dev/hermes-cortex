"""Input validation and sanitization.

All external inputs (Slack messages, tool outputs, memory retrievals)
must pass through validation before being used in prompts or operations.

Requirements: GEMINI.md §10, SEC-001
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hermes_mcp.logging import get_logger

logger = get_logger(__name__)

# Known prompt injection patterns (non-exhaustive, defense-in-depth)
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
        re.IGNORECASE,
    ),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"ASSISTANT:\s*", re.IGNORECASE),
]

# Maximum input lengths
MAX_SLACK_MESSAGE_LENGTH = 40000  # Slack's limit
MAX_TOOL_OUTPUT_LENGTH = 100000
MAX_SQL_QUERY_LENGTH = 10000
MAX_CODE_LENGTH = 50000


@dataclass(frozen=True)
class ValidationResult:
    """Result of input validation."""

    is_valid: bool
    sanitized_input: str = ""
    violations: list[str] = field(default_factory=list)


def validate_slack_message(text: str) -> ValidationResult:
    """Validate and sanitize a Slack message input.

    Args:
        text: Raw Slack message text.

    Returns:
        ValidationResult with sanitized input or violation details.
    """
    violations: list[str] = []

    if not text or not text.strip():
        return ValidationResult(is_valid=False, violations=["Empty input"])

    if len(text) > MAX_SLACK_MESSAGE_LENGTH:
        violations.append(f"Input exceeds maximum length ({MAX_SLACK_MESSAGE_LENGTH})")
        return ValidationResult(is_valid=False, violations=violations)

    # Check for prompt injection patterns
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            violations.append(f"Potential prompt injection detected: {pattern.pattern}")
            logger.warning(
                "prompt_injection_detected",
                pattern=pattern.pattern,
                input_length=len(text),
            )

    if violations:
        return ValidationResult(is_valid=False, violations=violations)

    # Sanitize: strip control characters except newlines and tabs
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return ValidationResult(is_valid=True, sanitized_input=sanitized)


def validate_sql_query(sql: str) -> ValidationResult:
    """Validate a SQL query for safety.

    Only SELECT statements are allowed. DDL, DML (INSERT/UPDATE/DELETE),
    and administrative commands are rejected.

    Args:
        sql: SQL query string.

    Returns:
        ValidationResult with validation outcome.
    """
    violations: list[str] = []

    if not sql or not sql.strip():
        return ValidationResult(is_valid=False, violations=["Empty SQL query"])

    if len(sql) > MAX_SQL_QUERY_LENGTH:
        violations.append(f"SQL query exceeds maximum length ({MAX_SQL_QUERY_LENGTH})")
        return ValidationResult(is_valid=False, violations=violations)

    normalized = sql.strip().upper()

    # Allowlist: only SELECT and WITH (CTE) queries
    if not normalized.startswith(("SELECT", "WITH", "EXPLAIN")):
        violations.append(
            "Only SELECT, WITH (CTE), and EXPLAIN queries are allowed",
        )

    # Blocklist: dangerous operations
    dangerous_patterns = [
        (
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b",
            "Mutation/DDL operation detected",
        ),
        (r"\b(COPY|pg_dump|pg_restore)\b", "Administrative operation detected"),
        (r"\bEXEC(UTE)?\b", "EXECUTE statement detected"),
        (r"\bINTO\s+OUTFILE\b", "File write operation detected"),
        (r"\bLOAD_FILE\b", "File read operation detected"),
        (r";\s*\w", "Multiple statements detected (potential SQL injection)"),
    ]

    for pattern, description in dangerous_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            violations.append(description)

    if violations:
        logger.warning("sql_validation_failed", violations=violations, query_length=len(sql))
        return ValidationResult(is_valid=False, violations=violations)

    return ValidationResult(is_valid=True, sanitized_input=sql.strip())


def validate_tool_output(output: str) -> ValidationResult:
    """Validate and sanitize tool output before including in prompts.

    Args:
        output: Raw tool output string.

    Returns:
        ValidationResult with sanitized output.
    """
    violations: list[str] = []

    if len(output) > MAX_TOOL_OUTPUT_LENGTH:
        # Truncate rather than reject, but note the truncation
        output = output[:MAX_TOOL_OUTPUT_LENGTH]
        violations.append(f"Output truncated to {MAX_TOOL_OUTPUT_LENGTH} characters")
        logger.info("tool_output_truncated", original_length=len(output))

    # Check for injection attempts in tool output
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(output):
            violations.append(f"Suspicious content in tool output: {pattern.pattern}")
            logger.warning("tool_output_injection_detected", pattern=pattern.pattern)

    # Strip potential HTML/script injection
    sanitized = re.sub(
        r"<script[^>]*>.*?</script>",
        "[SCRIPT_REMOVED]",
        output,
        flags=re.DOTALL | re.IGNORECASE,
    )
    sanitized = re.sub(
        r"<iframe[^>]*>.*?</iframe>",
        "[IFRAME_REMOVED]",
        sanitized,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return ValidationResult(
        is_valid=len(violations) == 0 or all("truncated" in v.lower() for v in violations),
        sanitized_input=sanitized,
        violations=violations,
    )
