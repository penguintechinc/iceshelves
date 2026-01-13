# Multi-stage Dockerfile for repo-worker service
# Python 3.13 async service for Docker/Helm repository

# =============================================================================
# Builder stage
# =============================================================================
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Runtime stage
# =============================================================================
FROM python:3.13-slim AS runtime

# Labels
LABEL org.opencontainers.image.title="repo-worker"
LABEL org.opencontainers.image.description="Multi-architecture Helm and Docker Repository Service"
LABEL org.opencontainers.image.vendor="Penguin Tech Inc"

# Create non-root user
RUN groupadd -r repoworker && useradd -r -g repoworker repoworker

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=repoworker:repoworker . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5050 \
    HOST=0.0.0.0 \
    WORKERS=4

# Switch to non-root user
USER repoworker

# Expose port
EXPOSE 5050

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/healthz')" || exit 1

# Run the application
CMD ["python", "run.py"]
