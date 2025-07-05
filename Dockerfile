# Multi-stage build for Meshtastic Matrix Relay
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and setup files
COPY requirements.txt setup.py setup.cfg pyproject.toml MANIFEST.in ./
COPY README.md ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir .

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    # For BLE support
    bluez \
    # For system utilities
    procps \
    # For timezone support
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mmrelay && useradd -r -g mmrelay -d /app -s /bin/bash mmrelay

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/mmrelay /usr/local/bin/mmrelay

# Create directories for data persistence
RUN mkdir -p /app/data /app/config /app/logs && \
    chown -R mmrelay:mmrelay /app

# Switch to non-root user
USER mmrelay

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose any ports if needed (none required for this app)
# EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f mmrelay || exit 1

# Default command
CMD ["mmrelay", "--config", "/app/config/config.yaml", "--data-dir", "/app/data", "--logfile", "/app/logs/mmrelay.log"]
