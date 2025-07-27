# Build stage
FROM python:3.11-slim AS builder

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

# Install dependencies and application package
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps .

# Runtime stage
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd --gid 1000 mmrelay && \
    useradd --uid 1000 --gid mmrelay --shell /bin/bash --create-home mmrelay

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    procps \
    && (apt-get install -y --no-install-recommends bluez || echo "Warning: bluez package not found for this architecture. BLE support will be unavailable.") \
    && rm -rf /var/lib/apt/lists/*

# Note: User will be set via docker-compose user directive

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy scripts to the correct location
COPY --from=builder /usr/local/bin/mmrelay /usr/local/bin/mmrelay

# Create app directory and set ownership
RUN mkdir -p /app && chown -R mmrelay:mmrelay /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PATH=/usr/local/bin:/usr/bin:/bin

# Switch to non-root user
USER mmrelay

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f mmrelay || exit 1

# Default command - uses config.yaml from volume mount
CMD ["mmrelay", "--config", "/app/config.yaml", "--data-dir", "/app/data", "--logfile", "/app/logs/mmrelay.log"]
