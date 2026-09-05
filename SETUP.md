# Hermes Cortex — Installation & Setup Guide

This guide provides step-by-step instructions for installing, configuring, and running **Hermes Cortex**, including how to obtain and configure all environment variables in your `.env` file.

---

## 1. Prerequisites

- **Python:** 3.11, 3.12, or 3.13
- **Git:** Installed and available on your PATH
- **Docker & Docker Compose (Optional):** Required only if you want to run local PostgreSQL, Redis, and Qdrant containers. The core agent and all 4 MCP servers can also run 100% locally with automated in-memory failover.

---

## 2. Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/msaif-dev/hermes-cortex.git
   cd hermes-cortex
   ```

2. **Create and activate a virtual environment:**
   - **On Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **On macOS/Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -e ".[dev,cli]"
   ```

4. **Initialize your environment file:**
   ```bash
   cp .env.example .env
   ```

---

## 3. How to Obtain & Configure `.env` Variables (Step-by-Step)

Open your newly created `.env` file. Below are the exact instructions to retrieve each value:

### 3.1 Google Gemini API Key
Hermes Cortex features native Google Gemini integration.

1. Navigate to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with your Google Account.
3. Click the **"Create API key"** button.
4. Select an existing Google Cloud project or click **"Create key in new project"**.
5. Copy your generated API key (it begins with `AIzaSy...`).
6. Paste it into your `.env` file:
   ```env
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-2.5-flash
   LLM_API_KEY=AIzaSyYourGeneratedKeyHere
   LLM_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/
   GEMINI_API_KEY=AIzaSyYourGeneratedKeyHere
   GOOGLE_API_KEY=AIzaSyYourGeneratedKeyHere
   ```
   > **Note:** `gemini-2.5-flash` is recommended for high-speed, cost-efficient analysis. If you need deep architectural reasoning, you can change `LLM_MODEL` to `gemini-2.5-pro`.

---

### 3.2 Slack Bot Credentials (For Slack Collaboration)
*(Optional: Only needed if you plan to deploy the agent to Slack. Skip if using CLI only.)*

1. Navigate to the [Slack API Portal](https://api.slack.com/apps).
2. Click **"Create New App"** → choose **"From scratch"**.
3. Name your app (e.g. `Hermes Cortex`) and choose your Slack Workspace.
4. **App-Level Token (`xapp-...`):**
   - In the left sidebar, click **"Basic Information"**.
   - Scroll down to **"App-Level Tokens"** and click **"Generate Token and Scopes"**.
   - Name the token `socket-token`.
   - Click **"Add Scope"** and select `connections:write`.
   - Click **Generate**, copy the token (starts with `xapp-`), and set:
     ```env
     SLACK_APP_TOKEN=xapp-your-app-token-here
     ```
5. **Enable Socket Mode:**
   - In the left sidebar, click **"Socket Mode"**.
   - Toggle **"Enable Socket Mode"** to **ON**.
6. **Bot Scopes & Bot Token (`xoxb-...`):**
   - In the left sidebar, click **"OAuth & Permissions"**.
   - Scroll down to **"Scopes"** → **"Bot Token Scopes"** and add:
     - `app_mentions:read`
     - `chat:write`
     - `channels:history`
     - `im:history`
     - `files:read`
     - `files:write`
   - Scroll to the top of the page and click **"Install to Workspace"** → click **Allow**.
   - Copy the **Bot User OAuth Token** (starts with `xoxb-`) and set:
     ```env
     SLACK_BOT_TOKEN=xoxb-your-bot-token-here
     ```
7. **Subscribe to Events:**
   - In the left sidebar, click **"Event Subscriptions"** → toggle to **ON**.
   - Under **"Subscribe to bot events"**, add `app_mention`.
   - Click **Save Changes**.

---

### 3.3 PostgreSQL Data Warehouse Credentials

- **If using Docker Compose:**
  The included `docker-compose.yml` automatically launches PostgreSQL and initializes `scripts/init-db.sql`. The default credentials match `.env`:
  ```env
  DB_HOST=localhost
  DB_PORT=5432
  DB_NAME=hermes
  DB_USER=hermes_readonly
  DB_PASSWORD=dev_readonly_password
  ```
- **If using an existing PostgreSQL instance:**
  Replace the host, port, database name, and read-only credentials with your existing database connection details.

---

### 3.4 Daytona Cloud Sandbox (Optional)

The execution sandbox server allows the agent to run Python scripts safely.

- **Option A (Default - Zero Setup):** Leave `DAYTONA_API_KEY` blank. The platform will automatically execute Python code in an **isolated local sub-process** with timeout limits and memory guards.
- **Option B (Cloud Container Sandboxes):**
  1. Sign up at [Daytona](https://app.daytona.io/).
  2. Go to **Settings > API Keys** → click **Create Key**.
  3. Copy the key and set:
     ```env
     DAYTONA_API_KEY=your-daytona-api-key
     DAYTONA_API_URL=https://app.daytona.io/api
     DAYTONA_TARGET=us
     ```

---

### 3.5 Observability & Runtime Settings

```env
APP_ENVIRONMENT=development
OBS_LOG_LEVEL=INFO
OBS_LOG_FORMAT=console
OBS_METRICS_ENABLED=true
OBS_METRICS_PORT=9090
OBS_TRACING_ENABLED=false
```

When `OBS_METRICS_ENABLED=true`, Prometheus metrics are automatically exposed at `http://localhost:9090/metrics` and service health at `http://localhost:9090/healthz`.

---

## 4. Starting the Platform

### Mode A: Interactive Terminal (Hermes CLI)
```bash
# Windows
.\hermes

# Linux / macOS
hermes
```

### Mode B: Docker Services & Slack Gateway
1. **Start the database and cache services:**
   ```bash
   docker compose up -d
   ```
2. **Start the Slack Gateway:**
   ```bash
   python -m hermes_mcp.gateway.slack_gateway
   ```

---

## 5. Automated Benchmarking

Run the automated performance benchmark suite across all 4 MCP servers, memory caching, and multi-step reasoning:

```bash
python scripts/run_benchmarks.py
```

This verifies latencies against SLA targets and outputs detailed statistical percentiles (min, max, mean, p95).

---

## 6. Verifying the Installation

Run the complete test suite and static analysis to confirm all components and quality gates pass:

```bash
# Run all 92 automated tests with coverage
pytest tests/ -v --cov=src/hermes_mcp

# Type checking
mypy src/ tests/ scripts/

# Linting & Formatting
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```
All **92 automated tests** should pass cleanly with zero linting or type errors.
