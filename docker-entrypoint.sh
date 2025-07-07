#!/bin/bash
set -e

# Fix permissions for mounted volumes
if [ -d "/app/data" ]; then
    chown -R mmrelay:mmrelay /app/data
fi

if [ -d "/app/logs" ]; then
    chown -R mmrelay:mmrelay /app/logs
fi

# Switch to mmrelay user and execute the command
exec gosu mmrelay "$@"
