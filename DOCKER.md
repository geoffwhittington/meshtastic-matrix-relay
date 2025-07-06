# Docker Deployment

Simple Docker setup for Meshtastic Matrix Relay.

## Quick Start

**Option 1: One-step setup (recommended for first time):**
```bash
make setup    # Copies config and opens your editor
make build    # Build Docker image
make run      # Start container
```

**Option 2: Manual steps:**
```bash
make config   # Copy sample config
make edit     # Edit config with your preferred editor
make build    # Build Docker image
make run      # Start container
```

## Commands

- `make setup` - Copy sample config and open editor (recommended for first time)
- `make config` - Copy sample config to ~/.mmrelay/config.yaml
- `make edit` - Edit config file with your preferred editor
- `make build` - Build Docker image with --no-cache for fresh builds
- `make rebuild` - Stop, rebuild, and restart container (for updates)
- `make run` - Start container
- `make stop` - Stop container
- `make logs` - Show container logs
- `make shell` - Access container shell
- `make clean` - Remove containers

## Connection Types

**TCP (recommended):**
- Works out of the box with `network_mode: host`
- Set `meshtastic.host` in ~/.mmrelay/config.yaml
- Meshtastic typically uses port 4403 for TCP connections

**Serial:**
- Uncomment device mapping in docker-compose.yaml
- Set `meshtastic.serial_port` in ~/.mmrelay/config.yaml

**BLE:**
- Uncomment `privileged: true` in docker-compose.yaml
- Set `meshtastic.ble_address` in ~/.mmrelay/config.yaml

## Data Persistence

Uses the same directories as standalone installation:

- **Config**: `~/.mmrelay/config.yaml` (mounted read-only)
- **Database**: `~/.mmrelay/data/` (persistent)
- **Logs**: `~/.mmrelay/logs/` (persistent)

This means your Docker and standalone installations share the same data!

## Updates

```bash
git pull
make rebuild    # Stop, rebuild with fresh code, and restart
```
