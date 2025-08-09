# Docker Deployment

MMRelay supports Docker deployment with two image options and multiple deployment methods.

## Table of Contents

- [Quick Start](#quick-start)
- [Deployment Methods](#deployment-methods)
  - [Method 1: Prebuilt Images (Recommended)](#method-1-prebuilt-images-recommended)
    - [Option A: With Make (from cloned repository)](#option-a-with-make-from-cloned-repository)
    - [Option B: Direct Docker Compose (no repo needed)](#option-b-direct-docker-compose-no-repo-needed)
    - [Option C: Portainer/GUI Tools](#option-c-portainergui-tools)
  - [Method 2: Build from Source](#method-2-build-from-source)
    - [Option A: With Make (build from source)](#option-a-with-make-build-from-source)
    - [Option B: Without Make](#option-b-without-make)
- [Environment Variables](#environment-variables)
- [Make Commands Reference](#make-commands-reference)
- [Connection Types](#connection-types)
- [Data Persistence](#data-persistence)
- [Troubleshooting](#troubleshooting)
- [Updates](#updates)

## Quick Start

**Most users should use Method 1, Option B** (prebuilt images without cloning):

```bash
# 1. Create directories and get config
mkdir -p ~/.mmrelay/data ~/.mmrelay/logs
curl -Lo ~/.mmrelay/config.yaml https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/main/src/mmrelay/tools/sample_config.yaml

# 2. Edit your config
nano ~/.mmrelay/config.yaml

# 3. Get docker-compose file and start
curl -o docker-compose.yaml https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/main/src/mmrelay/tools/sample-docker-compose-prebuilt.yaml
docker compose up -d
```

## Deployment Methods

Choose the method that best fits your needs:

### Method 1: Prebuilt Images (Recommended)

**Fast setup with official images** - no building required, perfect for most users.

- **Image**: `ghcr.io/jeremiah-k/mmrelay:latest`
- **Benefits**: Fastest setup, multi-platform (amd64/arm64), automatic updates
- **Best for**: Most users who want to run MMRelay quickly

#### Option A: With Make (from cloned repository)

If you've cloned the repository locally, use the convenient Make commands:

```bash
make setup-prebuilt  # Copy config, .env, and docker-compose.yaml, then opens editor
make run             # Start container (pulls official image)
make logs            # View logs
```

#### Option B: Direct Docker Compose (no repo needed)

**Complete setup without cloning the repository:**

```bash
# Step 1: Create directories
mkdir -p ~/.mmrelay/data ~/.mmrelay/logs

# Step 2: Download and edit config
curl -o ~/.mmrelay/config.yaml \
  https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/main/src/mmrelay/tools/sample_config.yaml
nano ~/.mmrelay/config.yaml  # Edit with your Matrix/Meshtastic settings

# Step 3: Download docker-compose file
curl -o docker-compose.yaml \
  https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/main/src/mmrelay/tools/sample-docker-compose-prebuilt.yaml

# Step 4: (Optional) Download .env for customization
curl -o .env \
  https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/main/src/mmrelay/tools/sample.env

# Step 5: Start the container
docker compose up -d

# View logs
docker compose logs -f
```

**Notes:**

- Skip the .env file if you want to use defaults (UID=1000, GID=1000, MMRELAY_HOME=$HOME)
- For BLE or Watchtower features, uncomment relevant sections in the docker-compose.yaml
- The container will automatically pull the latest official image

#### Option C: Portainer/GUI Tools

For users who prefer web-based Docker management:

1. **Create config file on your host:**

   ```bash
   mkdir -p ~/.mmrelay/data ~/.mmrelay/logs
   curl -o ~/.mmrelay/config.yaml https://raw.githubusercontent.com/jeremiah-k/meshtastic-matrix-relay/main/src/mmrelay/tools/sample_config.yaml
   nano ~/.mmrelay/config.yaml
   ```

2. **In Portainer, create a new Stack with this compose:**
   - Copy content from: [sample-docker-compose-prebuilt.yaml](https://github.com/jeremiah-k/meshtastic-matrix-relay/blob/main/src/mmrelay/tools/sample-docker-compose-prebuilt.yaml)
   - **Important:** Replace `${MMRELAY_HOME}` with your actual home directory path (e.g., `/home/username`)
   - Set environment variables in Portainer if needed (UID, GID, etc.)

3. **Minimal Portainer compose (if you prefer to start simple):**
   ```yaml
   services:
     mmrelay:
       image: ghcr.io/jeremiah-k/mmrelay:latest
       container_name: meshtastic-matrix-relay
       restart: unless-stopped
       user: "1000:1000"
       environment:
         - TZ=UTC
         - PYTHONUNBUFFERED=1
         - MPLCONFIGDIR=/tmp/matplotlib
       volumes:
         - /home/yourusername/.mmrelay/config.yaml:/app/config.yaml:ro
         - /home/yourusername/.mmrelay:/app/data
       ports:
         - "4403:4403"
   ```
   Replace `/home/yourusername` with your actual home directory.

### Method 2: Build from Source

**Full control with local compilation** - build your own image for development or customization.

- **Build**: Local compilation from source code
- **Benefits**: Full control, local modifications, development, latest features
- **Best for**: Developers, contributors, users who want customization

#### Option A: With Make (build from source)

If you've cloned the repository locally, use the convenient Make commands:

```bash
make setup    # Copy config, .env, and docker-compose.yaml, then opens editor
make build    # Build Docker image from source (uses layer caching)
make run      # Start container
make logs     # View logs
```

#### Option B: Without Make

If you prefer not to use Make commands, you can use the standard Docker Compose workflow:

```bash
# After cloning the repository:
make config  # Creates ~/.mmrelay/config.yaml, .env, and docker-compose.yaml
nano ~/.mmrelay/config.yaml  # Edit your settings

# Build and start:
docker compose build
docker compose up -d
docker compose logs -f
```

**Note:** The `make config` command is still the easiest way to set up the files correctly. Building from source without any Make commands would require manually creating all configuration files and is not recommended.

## Environment Variables

The docker-compose files use environment variables for customization:

- **`MMRELAY_HOME`**: Base directory for MMRelay data (default: `$HOME`)
- **`UID`**: User ID for container permissions (default: `1000`)
- **`GID`**: Group ID for container permissions (default: `1000`)
- **`EDITOR`**: Preferred text editor for config editing (default: `nano`)

These are set in the `.env` file. For Portainer users, you can:

1. Set them in Portainer's environment variables section
2. Use absolute paths instead of variables in the docker-compose
3. Ensure the paths exist on your host system

## Make Commands Reference

### Setup Commands

- `make setup-prebuilt` - Copy config for prebuilt images and open editor (recommended)
- `make setup` - Copy config for building from source and open editor
- `make config` - Copy sample files and create directories (config.yaml, .env, docker-compose.yaml)
- `make edit` - Edit config file with your preferred editor

### Container Management

- `make run` - Start container (prebuilt images or built from source)
- `make stop` - Stop container (keeps container for restart)
- `make logs` - Show container logs
- `make shell` - Access container shell
- `make clean` - Remove containers and networks

### Build Commands (Source Only)

- `make build` - Build Docker image from source (uses layer caching for faster builds)
- `make build-nocache` - Build Docker image from source with --no-cache for fresh builds
- `make rebuild` - Stop, rebuild with --no-cache, and restart container (for updates)

### Manual Docker Commands

If not using make commands:

```bash
# Start with prebuilt image
docker compose up -d

# Build and start from source
docker compose build
docker compose up -d

# View logs
docker compose logs -f

# Stop containers
docker compose down

# Access shell
docker compose exec mmrelay bash
```

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

- **Config**: `~/.mmrelay/config.yaml` (mounted read-only to `/app/config.yaml`)
- **Data Directory**: `~/.mmrelay/` (mounted to `/app/data` - contains database, logs, plugins)

**Volume Mounting Explanation:**
The Docker compose files mount `~/.mmrelay/` to `/app/data` which contains all persistent data (database, logs, plugins). The config file is also mounted separately to `/app/config.yaml` for clarity, even though it's technically accessible via the data mount. This dual mounting ensures the container can find the config file at the expected location.

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

## Troubleshooting

### Common Portainer Issues

**Volume path errors:**

- Ensure paths like `/home/yourusername/.mmrelay/` exist on the host
- Replace `yourusername` with your actual username
- Create directories manually: `mkdir -p ~/.mmrelay/data ~/.mmrelay/logs`

**Permission errors:**

- Check that the user ID (1000) has access to the mounted directories
- Adjust `UID` and `GID` in environment variables if needed
- Use `chown -R 1000:1000 ~/.mmrelay/` to fix ownership

**Environment variable issues:**

- Portainer doesn't expand `$HOME` - use absolute paths
- Set environment variables in Portainer's stack environment section
- Or replace `${MMRELAY_HOME}` with absolute paths in the compose file

**Config file not found:**

- Verify the config file exists at the mounted path
- Check the volume mapping in the compose file
- Ensure the file is readable by the container user

### General Docker Issues

**Container won't start:**

- Check logs: `docker compose logs mmrelay`
- Verify config file syntax: `mmrelay --config ~/.mmrelay/config.yaml --validate`
- Ensure all required config fields are set

**Connection issues:**

- For TCP: Verify Meshtastic device IP and port 4403
- For Serial: Check device permissions and path
- For BLE: Ensure privileged mode and host networking are enabled

## Updates

**Prebuilt images:**

- Pull latest: `docker compose pull && docker compose up -d`
- Or use Watchtower for automatic updates (see sample-docker-compose-prebuilt.yaml)

**Built from source:**

```bash
git pull
make rebuild    # Stop, rebuild with fresh code, and restart
```
