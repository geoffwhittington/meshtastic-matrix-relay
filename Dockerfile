# Build stage
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy source files
COPY requirements.txt setup.py ./
COPY README.md ./
COPY src/ ./src/

# Build wheels
RUN pip wheel --no-cache-dir . -w /wheels

# Runtime stage
FROM python:3.11-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && (apt-get install -y --no-install-recommends bluez || echo "bluez not available on this architecture") \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mmrelay && useradd -r -g mmrelay -d /app -s /bin/bash mmrelay

# Set working directory
WORKDIR /app

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Install application from pre-built wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels mmrelay \
    && rm -rf /wheels

# Create directories and set permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R mmrelay:mmrelay /app

# Switch to non-root user
USER mmrelay

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f mmrelay || exit 1

# Default command - uses config.yaml from volume mount
CMD ["mmrelay", "--config", "/app/config.yaml", "--data-dir", "/app/data", "--logfile", "/app/logs/mmrelay.log"]
