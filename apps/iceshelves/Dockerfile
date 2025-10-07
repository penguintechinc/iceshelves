# IceShelves Dockerfile
# Multi-stage build for optimized production image

# Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim

LABEL maintainer="Penguin Tech Inc <info@penguintech.group>"
LABEL description="IceShelves - LXD/KVM Egg Deployment Platform"
LABEL version="1.0.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 iceshelves

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/iceshelves/.local

# Copy application code
COPY . /app/

# Set ownership
RUN chown -R iceshelves:iceshelves /app

# Switch to non-root user
USER iceshelves

# Add local bin to PATH
ENV PATH=/home/iceshelves/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/iceshelves/healthz || exit 1

# Run py4web
CMD ["py4web", "run", "apps", "--host", "0.0.0.0", "--port", "8000", "--watch", "off"]
