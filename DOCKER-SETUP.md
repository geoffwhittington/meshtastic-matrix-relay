# Complete Docker Setup Guide

## Auto-Building Docker Images

### Option 1: Using Your Fork (Recommended)

Since you can't store secrets in the main repo, use your fork for automated builds:

1. **Set up Docker Hub secrets in your fork:**
   - Go to your fork: `https://github.com/jeremiah-k/meshtastic-matrix-relay`
   - Settings → Secrets and variables → Actions
   - Add these secrets:
     - `DOCKER_USERNAME`: Your Docker Hub username
     - `DOCKER_TOKEN`: Your Docker Hub access token

2. **The workflow will automatically:**
   - Build on every release/tag
   - Build multi-architecture images (amd64, arm64, armv7)
   - Push to Docker Hub as `yourusername/mmrelay:latest`
   - Update Docker Hub description

3. **To trigger a build:**
   ```bash
   git tag v1.0.13
   git push jkfork v1.0.13
   ```

### Option 2: Manual Build and Push

```bash
# Build locally
docker build -t yourusername/mmrelay:latest .

# Push to Docker Hub
docker push yourusername/mmrelay:latest
```

## Understanding the Docker Setup

### Why This Complexity?

This setup follows Docker best practices:

1. **Multi-stage build**: Reduces image size by ~60%
2. **Security**: Non-root user, minimal attack surface  
3. **Production-ready**: Health checks, logging, persistence
4. **Flexibility**: Supports TCP/Serial/BLE connections

### Makefile Explained

**What is `.PHONY`?**
- Tells make these are commands, not files
- Without it, if you had a file named "build", make would skip the command

**How to use:**
```bash
make help           # Show all available commands
make generate-compose  # Generate docker-compose from config
make config         # Copy sample config
make build          # Build Docker image  
make run            # Start container
make logs           # Show logs
make shell          # Access container
make backup         # Backup data
make clean          # Remove everything
```

**This is much easier than remembering:**
```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
docker-compose exec mmrelay bash
```

## Configuration Management

### Keeping Config and Docker-Compose in Sync

The `generate-docker-compose.py` script ensures consistency:

```bash
# Generate a new docker-compose based on sample config
make generate-compose

# Compare with existing
diff docker-compose.yml docker-compose.generated.yml

# Update if needed
mv docker-compose.generated.yml docker-compose.yml
```

### Connection Types

**TCP (Recommended for Docker):**
```yaml
meshtastic:
  connection_type: "tcp"
  host: "192.168.1.100"
```
- Uses `network_mode: host`
- No special Docker configuration needed

**Serial:**
```yaml
meshtastic:
  connection_type: "serial"  
  serial_port: "/dev/ttyUSB0"
```
- Requires device mapping in docker-compose.yml
- Uncomment the devices section

**BLE:**
```yaml
meshtastic:
  connection_type: "ble"
  ble_address: "AA:BB:CC:DD:EE:FF"  
```
- Requires `privileged: true` or specific capabilities
- Uses `network_mode: host`

## Quick Start Workflow

1. **Initial setup:**
   ```bash
   make config          # Copy sample config
   # Edit config.yaml for your setup
   make build           # Build image
   make run             # Start container
   ```

2. **Daily operations:**
   ```bash
   make logs            # Check logs
   make shell           # Access container
   make backup          # Backup data
   ```

3. **Updates:**
   ```bash
   git pull jkfork main
   make build
   make restart
   ```

## Production Deployment

### Security Checklist
- [ ] Non-root user (✅ included)
- [ ] Read-only config mount (✅ included)  
- [ ] Resource limits (add to docker-compose.yml)
- [ ] Network isolation (configure as needed)
- [ ] Regular backups (✅ make backup)

### Monitoring
- Health checks included
- Log rotation configured
- Use `docker-compose ps` to check status

### Scaling
- Single container design (stateful)
- Use volumes for data persistence
- Consider external database for high availability

This setup provides enterprise-grade Docker deployment while remaining simple to use.
