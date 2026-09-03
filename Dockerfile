# Multi-stage Dockerfile for Hermes MCP Platform
# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache -e ".[dev]"

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user
RUN groupadd -r hermes && useradd -r -g hermes -d /app -s /sbin/nologin hermes

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY config/config.example.yaml ./config/config.example.yaml

# Set ownership
RUN chown -R hermes:hermes /app

# Switch to non-root user
USER hermes

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import hermes_mcp; print('healthy')" || exit 1

ENTRYPOINT ["python", "-m"]
CMD ["hermes_mcp"]
