# Hermes Cortex

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-2.0%2B-green.svg)](https://modelcontextprotocol.io/)
[![Runtime](https://img.shields.io/badge/Runtime-Hermes%20Agent%200.19.0-purple.svg)](https://hermes-agent.nousresearch.com/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-92%20Passing-success.svg)]()
[![Coverage](https://img.shields.io/badge/Coverage-81%25-success.svg)]()

**Hermes Cortex** is an enterprise-grade autonomous research and data engineering platform. Powered by the **Hermes Agent** runtime and the **Model Context Protocol (MCP)**, it empowers analysts and engineers to securely query production databases, search internal documentation, inspect codebases, run sandboxed Python computations, and analyze uploaded datasets through conversational interfaces and automated pipelines.

---

## Quick Navigation

- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [MCP Tool Servers](#mcp-tool-servers)
- [Setup & Environment Guide (SETUP.md)](SETUP.md)
- [Quick Start](#quick-start)
- [Automated Benchmarks & SLA Verification](#automated-benchmarks--sla-verification)
- [Verification & Quality Gates](#verification--quality-gates)

> [!IMPORTANT]
> For a step-by-step walkthrough on how to obtain your **LLM API Key**, configure **Slack Tokens**, and set up all environment variables, see the **[Complete Setup Guide (SETUP.md)](SETUP.md)**.

---

## Architecture Overview

Hermes Cortex implements a decoupled 3-tier architecture:

```mermaid
graph TD
    User([Analyst / Engineer via Slack or Terminal]) <--> Gateway[Tier 1: Slack Bolt Gateway / CLI]
    Gateway <--> Core[Tier 2: Hermes Agent Runtime]

    subgraph "Tier 2: Agent Intelligence & Governance"
        Core --> Planner[Task Planner]
        Core --> Reflexion[Reflexion Evaluator]
        Core --> Memory[Layered Memory & Semantic Cache]
        Core --> Auth[Tool Authorizer & HITL Approval]
        Core --> Observability[Prometheus & OpenTelemetry Tracing]
    end

    subgraph "Tier 3: MCP Tool Servers"
        Core <--> MCP1[Document Search Server]
        Core <--> MCP2[PostgreSQL Query Server]
        Core <--> MCP3[Code Search Server]
        Core <--> MCP4[Execution Sandbox Server]
    end

    subgraph "Storage & Infrastructure"
        MCP2 <--> DB[(PostgreSQL Warehouse)]
        MCP4 <--> Sandbox[(Daytona / Isolated Subprocess)]
        Memory <--> Cache[(Redis / Valkey Cache)]
        Memory <--> Vector[(Qdrant Vector Store)]
    end
```

---

## Key Features

- **Hermes Agent Runtime (`hermes-agent==0.19.0`):** Native Model Context Protocol (MCP) client, multi-turn reasoning loops, and multi-provider management.
- **Deterministic SQL Safety:** Read-only query enforcement (only `SELECT`, CTE `WITH`, and `EXPLAIN` queries are executed; destructive mutations are blocked).
- **Sandboxed Code Execution:** Dynamic Python execution in isolated Daytona cloud containers or restricted local sub-processes with resource guards and timeouts.
- **Multimodal File Attachments:** Ingestion of CSV, TSV, JSON, SQL, Python, and markdown files via Slack Bolt gateway with 10MB limits and virus/path traversal protections.
- **Layered Memory & Semantic Caching:** Session history, episodic execution traces, Qdrant vector memory, and tenant-isolated Redis semantic caching.
- **Full Observability & Distributed Tracing:** Native Prometheus metrics endpoint (`http://localhost:9090/metrics`), OpenTelemetry distributed spans across tool and agent lifecycles, and structured JSON logging.
- **Human-in-the-Loop (HITL) Governance:** Risk-tiered authorization workflows with explicit approval requirements for high-impact actions.

---

## MCP Tool Servers

| Server | Exposed Tools | Capabilities & Safety Guarantees |
| :--- | :--- | :--- |
| **PostgreSQL Query** | `run_sql`, `list_tables` | Deterministic read-only SQL validation; rejects all mutations; connection pooling via `asyncpg` with fail-fast timeouts. |
| **Document Search** | `search_docs` | Dynamic workspace indexing, relevance ranking, category-based metadata filtering, bounded excerpt generation. |
| **Code Search** | `search_code` | Path traversal protection (`../` blocked), regex search, exclusion of sensitive files (`.env`, `.pem`). |
| **Execution Sandbox** | `run_python` | Daytona cloud container isolation with local isolated subprocess fallback; strict 30s execution timeout. |

---

## Quick Start

### 1. Installation & Environment Configuration
Follow the **[Setup Guide (SETUP.md)](SETUP.md)** to install dependencies and create your `.env` file with your LLM API key:

```bash
# Clone the repository
git clone https://github.com/msaif-dev/hermes-cortex.git
cd hermes-cortex

# Install dependencies
pip install -e ".[dev,cli]"

# Configure environment
cp .env.example .env
# Edit .env and configure your LLM API key (see SETUP.md for details)
```

### 2. Launch the Interactive Agent
```bash
# Windows
.\hermes

# Linux / macOS
hermes
```

### 3. Example Queries
Once inside the Hermes shell, you can interact with all MCP tools in natural language:

- *"List all public tables in our database using postgres_query, and show the top 5 rows."*
- *"Search our analytical documents for recent architecture decisions."*
- *"Execute a Python script in execution_sandbox to compute a rolling average of revenue."*

---

## Automated Benchmarks & SLA Verification

Hermes Cortex includes a dedicated benchmark suite that executes automated synthetic and integration scenarios across all MCP tools, measuring latency percentiles (min, max, mean, p95) and validating against SLA ceilings:

```bash
python scripts/run_benchmarks.py
```

### Benchmark Results Summary

| Scenario | Complexity | Mean Latency | p95 Latency | Target SLA | Success Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Single Doc Search** | Low (1 tool) | 6.3 ms | 6.8 ms | < 2000 ms | 100.0% | **PASS** |
| **Safe SQL Execution** | Low (1 tool) | 1014.4 ms | 1015.5 ms | < 3000 ms | 100.0% | **PASS** |
| **Codebase Pattern Search** | Med (1 tool) | 12.5 ms | 14.2 ms | < 5000 ms | 100.0% | **PASS** |
| **Sandbox Code Run** | Med (1 tool) | 65.9 ms | 73.5 ms | < 10000 ms | 100.0% | **PASS** |
| **Semantic Cache Hit** | Micro (<50ms) | 0.1 ms | 0.1 ms | < 50 ms | 100.0% | **PASS** |
| **Multi-step Analysis** | High (3+ tools)| 4033.2 ms | 4591.8 ms | < 20000 ms | 100.0% | **PASS** |

---

## Verification & Quality Gates

Run the automated test suite and static analysis checks:

```bash
# 1. Run all 92 unit, integration, and smoke tests with coverage analysis
pytest tests/ -v --cov=src/hermes_mcp

# 2. Strict static type analysis
mypy src/ tests/ scripts/

# 3. Linting and format checks
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
