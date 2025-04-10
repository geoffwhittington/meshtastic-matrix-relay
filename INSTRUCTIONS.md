# MMRelay Instructions

MMRelay works on Linux, macOS, and Windows and requires Python 3.9+.

## Installation

### Quick Install (Recommended)

```bash
# Install using pip
pip install mmrelay

# Or use pipx for isolated installation (recommended)
pipx install mmrelay
```

### Developer Install

If you want to contribute or modify the code:

```bash
# Clone the repository
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
cd meshtastic-matrix-relay

# Install in development mode
pip install -e .

# Or use pipx for isolated installation
pipx install -e .
```

> **Upgrading from a previous version?** Please see [UPGRADE_TO_V1.md](UPGRADE_TO_V1.md) for migration guidance.

## Configuration

### Configuration File Locations

MMRelay looks for configuration files in the following locations (in order):

1. Path specified with `--config` command-line option
2. `~/.mmrelay/config.yaml` (recommended location)
3. Current directory `config.yaml`
4. Current directory `sample_config.yaml`

### Setting Up Your Configuration

```bash
# Create the standard config directory
mkdir -p ~/.mmrelay

# Copy the sample configuration
cp sample_config.yaml ~/.mmrelay/config.yaml

# Edit the configuration file with your preferred editor
nano ~/.mmrelay/config.yaml
```

### Configuration Tips

- Review the comments in `sample_config.yaml` for detailed explanations
- At minimum, you'll need to configure your Matrix credentials and Meshtastic connection
- For advanced setups, check the plugin configuration options

## Running MMRelay

### Basic Usage

Start the relay with a single command:

```bash
mmrelay
```

### Command-Line Options

Customize your setup with command-line options:

```bash
mmrelay --config /path/to/config.yaml --logfile /path/to/logfile.log
```

```
mmrelay [OPTIONS]

Options:
  --config PATH    Path to the configuration file
  --logfile PATH   Path to the log file
  --version        Show the version number and exit
  --help           Show this help message and exit
```

### What to Expect

When running successfully, you'll see output similar to this:

```
INFO: Loading configuration from: /home/user/.mmrelay/config.yaml
INFO: Starting Meshtastic <==> Matrix Relay...
INFO: Connecting to radio at meshtastic.local ...
INFO: Connected to radio at meshtastic.local
INFO: Listening for inbound radio messages ...
INFO: Listening for inbound matrix messages ...
```

Messages will be relayed in both directions automatically:

## Running as a Service

### Systemd Service (Linux)

For automatic startup and management on Linux systems:

1. Create the systemd user directory:
   ```bash
   mkdir -p ~/.config/systemd/user
   ```

2. Create a service file with this one-liner (automatically uses your mmrelay path):
   ```bash
   cat > ~/.config/systemd/user/mmrelay.service << EOL
   [Unit]
   Description=Meshtastic <==> Matrix Relay
   After=default.target

   [Service]
   Type=idle
   ExecStart=$(which mmrelay) --config %h/.mmrelay/config.yaml --logfile %h/.mmrelay/logs/mmrelay.log
   Restart=on-failure

   [Install]
   WantedBy=default.target
   EOL
   ```

3. Enable and start the service:
   ```bash
   # Reload systemd to recognize the new service
   systemctl --user daemon-reload

   # Enable the service to start at login
   systemctl --user enable mmrelay.service

   # Start the service now
   systemctl --user start mmrelay.service
   ```

4. Verify it's running correctly:
   ```bash
   systemctl --user status mmrelay.service
   ```

5. View logs if needed:
   ```bash
   # View service logs
   journalctl --user -u mmrelay.service

   # Or check the application log file
   cat ~/.mmrelay/logs/mmrelay.log
   ```

## Dockerized Versions (Unofficial)

If you would prefer to use a Dockerized version of the relay, there are unofficial third-party projects available. Please note that these are not officially supported, and issues should be reported to their respective repositories. For more details, visit the [Third Party Projects](https://github.com/geoffwhittington/meshtastic-matrix-relay/wiki/Third-Party-Projects) page.

## Development

### Contributing

Contributions are welcome! We use **Trunk** for automated code quality checks and formatting. The `trunk` launcher is committed directly to the repo, please run checks before submitting pull requests.

```bash
.trunk/trunk check --all --fix
```
