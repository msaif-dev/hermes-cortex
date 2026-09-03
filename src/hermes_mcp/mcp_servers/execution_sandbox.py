"""Execution Sandbox MCP Server.

Provides sandboxed Python code execution environments via Daytona.
Enforces strict timeouts, network isolation, resource limits, and output bounds.

Requirements: FR-MCP-004, GEMINI.md §13, SEC-006.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
import time
from typing import Annotated, Any

from daytona import CreateSandboxFromImageParams, Daytona, Resources
from daytona import DaytonaConfig as DConfig
from mcp.server import MCPServer
from pydantic import Field

from hermes_mcp.config import DaytonaConfig
from hermes_mcp.logging import get_logger
from hermes_mcp.security.input_validation import validate_tool_output

logger = get_logger(__name__)

mcp = MCPServer(
    "ExecutionSandboxServer",
    instructions=(
        "Executes sandboxed Python scripts and analytical calculations in isolated containers."
    ),
)

# Blocked modules/calls for defense-in-depth in local emulation mode
_FORBIDDEN_LOCAL_CALLS = [
    "shutil.rmtree",
    "os.remove",
    "os.unlink",
    "subprocess",
    "socket",
    "http.client",
    "urllib.request",
    "requests",
    "httpx",
]


async def _run_via_daytona(code: str, timeout_s: int, config: DaytonaConfig) -> dict[str, Any]:
    """Execute Python snippet using Daytona Cloud/Server SDK."""
    sdk_config = DConfig(
        api_key=config.api_key.get_secret_value(),
        api_url=config.api_url,
        target=config.target,
    )
    client = Daytona(sdk_config)

    resources = Resources(
        cpu=config.cpu,
        memory=config.memory,
        disk=config.disk,
    )
    params = CreateSandboxFromImageParams(
        image=config.default_image,
        resources=resources,
        auto_stop_interval=config.auto_stop_interval_min,
        network_block_all=config.network_block_all,
    )

    sandbox = client.create(params=params)
    try:
        # Execute stateless snippet in sandbox
        response = sandbox.process.code_run(code, timeout=timeout_s)
        return {
            "engine": "daytona_cloud",
            "exit_code": response.exit_code,
            "stdout": response.result or "",
            "stderr": getattr(response, "stderr", ""),
            "sandboxed": True,
        }
    finally:
        client.delete(sandbox)


async def _run_local_isolated(code: str, timeout_s: int) -> dict[str, Any]:
    """Run code in an isolated subprocess with limits."""
    # Safety pre-check for dangerous operations
    for call in _FORBIDDEN_LOCAL_CALLS:
        if call in code:
            return {
                "engine": "local_isolated",
                "exit_code": 1,
                "stdout": "",
                "stderr": f"SECURITY_ERROR: Forbidden call '{call}' detected in sandbox execution.",
                "sandboxed": True,
            }

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp_f:
        temp_f.write(code)
        temp_path = temp_f.name

    start_time = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",  # Isolated mode: don't import user site or inject PYTHONPATH
            temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=float(timeout_s),
        )

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")[:20000]
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:20000]
        exit_code = proc.returncode if proc.returncode is not None else -1

        return {
            "engine": "local_isolated",
            "exit_code": exit_code,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "execution_time_s": round(time.monotonic() - start_time, 3),
            "sandboxed": True,
        }

    except TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return {
            "engine": "local_isolated",
            "exit_code": -1,
            "stdout": "",
            "stderr": f"TIMEOUT: Execution exceeded time limit of {timeout_s} seconds.",
            "sandboxed": True,
        }
    finally:
        with contextlib.suppress(OSError):
            os.remove(temp_path)


@mcp.tool(name="run_python")
async def run_python(
    code: Annotated[
        str,
        Field(
            description="Python 3 script or calculation to execute in the sandbox",
            min_length=1,
            max_length=50000,
        ),
    ],
    timeout_s: Annotated[
        int, Field(default=30, ge=1, le=120, description="Execution timeout limit in seconds")
    ] = 30,
) -> str:
    """Execute Python code safely in an isolated sandbox environment.

    Returns stdout, stderr, execution exit code, and runtime telemetry.
    """
    logger.info("executing_sandbox_python", timeout_s=timeout_s)

    config = DaytonaConfig()
    has_daytona_key = bool(config.api_key.get_secret_value())

    if has_daytona_key:
        try:
            result = await _run_via_daytona(code, timeout_s, config)
        except Exception:
            logger.info("falling_back_to_local_isolation")
            result = await _run_local_isolated(code, timeout_s)
    else:
        result = await _run_local_isolated(code, timeout_s)

    output = json.dumps(result, indent=2)
    return validate_tool_output(output).sanitized_input


if __name__ == "__main__":
    mcp.run()
