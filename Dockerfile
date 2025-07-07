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
COPY requirements.txt setup.py setup.cfg ./
COPY README.md ./
COPY src/ ./src/

# Install application and dependencies to a target directory
RUN pip install --no-cache-dir --target=/install .

# Runtime stage
FROM python:3.11-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    procps \
    gosu \
    && (apt-get install -y --no-install-recommends bluez || echo "Warning: bluez package not found for this architecture. BLE support will be unavailable.") \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mmrelay && useradd -r -g mmrelay -d /app -s /bin/bash mmrelay

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local/lib/python3.11/site-packages

# Copy scripts to the correct location
COPY --from=builder /install/bin/* /usr/local/bin/

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directories and set permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R mmrelay:mmrelay /app && \
    chmod -R 755 /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f mmrelay || exit 1

# Set entrypoint and default command
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["mmrelay", "--config", "/app/config.yaml", "--data-dir", "/app/data", "--logfile", "/app/logs/mmrelay.log"]
