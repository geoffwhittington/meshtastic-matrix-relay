# Docker Deployment

MMRelay offers two Docker deployment options to suit different needs.

## Deployment Options

### Option 1: Prebuilt Images (Recommended)

Use official multi-platform images for fastest setup. No building required.

**Quick setup:**
```bash
make setup-prebuilt  # Copy config, .env, and docker-compose.yaml, then opens editor
make run             # Start container (pulls official image)
```

**Manual steps:**
```bash
make config          # Copy sample files and create directories
make edit            # Edit config with your preferred editor
# Copy prebuilt docker-compose manually if needed:
cp src/mmrelay/tools/sample-docker-compose-prebuilt.yaml docker-compose.yaml
make run             # Start container
```

### Option 2: Build from Source

Build your own image locally. Useful for development or custom modifications.

**Quick setup:**
```bash
make setup    # Copy config, .env, and docker-compose.yaml, then opens editor
make build    # Build Docker image from source
make run      # Start container
```

**Manual steps:**
```bash
make config   # Copy sample files and create directories
make edit     # Edit config with your preferred editor
make build    # Build Docker image from source
make run      # Start container
```

## Commands

### Setup Commands
- `make setup-prebuilt` - Copy config for prebuilt images and open editor (recommended)
- `make setup` - Copy config for building from source and open editor
- `make config` - Copy sample files and create directories (config.yaml, .env, docker-compose.yaml)
- `make edit` - Edit config file with your preferred editor

### Build Commands (Source Only)
- `make build` - Build Docker image from source (uses layer caching for faster builds)
- `make build-nocache` - Build Docker image from source with --no-cache for fresh builds
- `make rebuild` - Stop, rebuild with --no-cache, and restart container (for updates)
- `make run` - Start container
- `make stop` - Stop container (keeps container for restart)
- `make logs` - Show container logs
- `make shell` - Access container shell
- `make clean` - Remove containers and networks

## Connection Types

**TCP (recommended):**

- Uses port mapping for cross-platform compatibility
- Set `meshtastic.host` in ~/.mmrelay/config.yaml
- Meshtastic typically uses port 4403 for TCP connections
- Container exposes port 4403 to host

**Serial:**

- Uncomment device mapping in docker-compose.yaml
- Set `meshtastic.serial_port` in ~/.mmrelay/config.yaml

**BLE:**

- Uncomment the BLE section in docker-compose.yaml (includes privileged mode, host networking, and D-Bus access)
- Set `meshtastic.ble_address` in ~/.mmrelay/config.yaml
- Note: BLE requires host networking mode which may affect port isolation

## Data Persistence

Uses the same directories as standalone installation:

- **Config**: `~/.mmrelay/config.yaml` (mounted read-only)
- **Database**: `~/.mmrelay/data/` (persistent)
- **Logs**: `~/.mmrelay/logs/` (persistent)

This means your Docker and standalone installations share the same data!

**Environment Configuration:**
Docker Compose uses the `.env` file to set data directory paths. The `make config` command creates this automatically with:

```bash
MMRELAY_HOME=$HOME
```

**Custom Data Location:**
To use a different location, edit the `.env` file:

```bash
MMRELAY_HOME=/path/to/your/data
```

## Updates

```bash
git pull
make rebuild    # Stop, rebuild with fresh code, and restart
```
