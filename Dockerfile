FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    bluez \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mmrelay && useradd -r -g mmrelay -d /app -s /bin/bash mmrelay

# Set working directory
WORKDIR /app

# Copy and install application
COPY requirements.txt setup.py ./
COPY README.md ./
COPY src/ ./src/

# Install Python dependencies and application
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

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
