# Docker Deployment

Simple Docker setup for Meshtastic Matrix Relay.

## Quick Start

1. **Copy sample configuration:**

   ```bash
   make config
   ```

2. **Edit ~/.mmrelay/config.yaml** with your Matrix and Meshtastic settings

3. **Start the container:**
   ```bash
   make build
   make run
   ```

## Commands

- `make config` - Copy sample config to ~/.mmrelay/config.yaml
- `make build` - Build Docker image
- `make run` - Start container
- `make stop` - Stop container
- `make logs` - Show logs
- `make shell` - Access container shell
- `make clean` - Remove containers and volumes

## Connection Types

**TCP (recommended):**

- Works out of the box with `network_mode: host`
- Set `meshtastic.host` in ~/.mmrelay/config.yaml

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
make build
make stop
make run
```
