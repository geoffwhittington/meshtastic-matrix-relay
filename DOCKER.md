# Docker Deployment

Simple Docker setup for Meshtastic Matrix Relay.

## Quick Start

1. **Copy sample configuration:**

   ```bash
   make config
   ```

2. **Edit config.yaml** with your Matrix and Meshtastic settings

3. **Start the container:**
   ```bash
   make build
   make run
   ```

## Commands

- `make config` - Copy sample config file
- `make build` - Build Docker image
- `make run` - Start container
- `make stop` - Stop container
- `make logs` - Show logs
- `make shell` - Access container shell
- `make clean` - Remove containers and volumes

## Connection Types

**TCP (recommended):**

- Works out of the box with `network_mode: host`
- Set `meshtastic.host` in config.yaml

**Serial:**

- Uncomment device mapping in docker-compose.yaml
- Set `meshtastic.serial_port` in config.yaml

**BLE:**

- Uncomment `privileged: true` in docker-compose.yaml
- Set `meshtastic.ble_address` in config.yaml

## Data Persistence

- Database: `/app/data` (persistent volume)
- Logs: `/app/logs` (persistent volume)
- Config: `./config.yaml` (mounted read-only)

## Updates

```bash
git pull
make build
make stop
make run
```
