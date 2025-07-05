# Docker Deployment Guide

This guide explains how to deploy Meshtastic Matrix Relay using Docker.

## Quick Start

1. **Copy the sample configuration:**
   ```bash
   cp docker-config.yaml config.yaml
   ```

2. **Edit the configuration:**
   - Update Matrix homeserver, username, and password/token
   - Configure your Meshtastic connection (TCP/Serial/BLE)
   - Set up Matrix room mappings

3. **Start the container:**
   ```bash
   docker-compose up -d
   ```

## Configuration

### Matrix Setup
Edit `config.yaml` and configure your Matrix connection:
```yaml
matrix:
  homeserver: "https://your-matrix-server.org"
  username: "@your-bot:your-matrix-server.org"
  password: "your-bot-password"
```

### Meshtastic Connection Types

#### TCP Connection (Recommended for Docker)
```yaml
meshtastic:
  connection_type: "tcp"
  host: "192.168.1.100"  # IP of your Meshtastic device
```

#### Serial Connection
For serial connections, you need to:
1. Uncomment the device mapping in `docker-compose.yml`
2. Update the configuration:
```yaml
meshtastic:
  connection_type: "serial"
  serial_port: "/dev/ttyUSB0"
```

#### BLE Connection
For BLE connections:
1. Ensure `privileged: true` is set in `docker-compose.yml`
2. Update the configuration:
```yaml
meshtastic:
  connection_type: "ble"
  ble_address: "AA:BB:CC:DD:EE:FF"
```

## Volume Mounts

The Docker setup uses the following volumes:
- `./config.yaml:/app/config/config.yaml:ro` - Configuration file (read-only)
- `mmrelay_data:/app/data` - Database and persistent data
- `mmrelay_logs:/app/logs` - Log files

## Building from Source

To build the Docker image locally:
```bash
docker build -t mmrelay:local .
```

Then update `docker-compose.yml` to use your local image:
```yaml
services:
  mmrelay:
    image: mmrelay:local
    # Remove the 'build: .' line
```

## Troubleshooting

### Check container logs:
```bash
docker-compose logs -f mmrelay
```

### Access container shell:
```bash
docker-compose exec mmrelay bash
```

### Check container health:
```bash
docker-compose ps
```

### Restart the service:
```bash
docker-compose restart mmrelay
```

## Security Considerations

- The container runs as a non-root user (`mmrelay`)
- For BLE access, `privileged: true` is required but can be replaced with specific capabilities
- Configuration file is mounted read-only
- Consider using Docker secrets for sensitive data in production

## Environment Variables

You can override configuration using environment variables:
- `TZ` - Timezone (default: UTC)
- `PYTHONUNBUFFERED` - Python output buffering (set to 1)

## Updates

To update to a newer version:
1. Pull the latest image: `docker-compose pull`
2. Restart the container: `docker-compose up -d`

## Data Backup

Important data is stored in named volumes. To backup:
```bash
docker run --rm -v mmrelay_data:/data -v $(pwd):/backup alpine tar czf /backup/mmrelay-data-backup.tar.gz -C /data .
```

To restore:
```bash
docker run --rm -v mmrelay_data:/data -v $(pwd):/backup alpine tar xzf /backup/mmrelay-data-backup.tar.gz -C /data
```
