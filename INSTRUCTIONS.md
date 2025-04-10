# Instructions

The relay works on Linux, macOS, and Windows and requires Python 3.9+.

## Installation

### Install from PyPI (Recommended)

```bash
# Install using pip
pip install mmrelay

# Or use pipx for isolated installation (recommended)
pipx install mmrelay
```

### Install from Source

```bash
# Clone the repository
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
cd meshtastic-matrix-relay

# Install using pip
pip install -e .

# Or use pipx for isolated installation (recommended)
pipx install -e .
```

> **Note:** If you're upgrading from a previous version, please refer to the [UPGRADE_TO_V1.md](UPGRADE_TO_V1.md) file for migration instructions.

## Configuration

The application looks for configuration files in the following locations (in order):

1. Path specified with `--config` command-line option
2. `~/.mmrelay/config.yaml`
3. Current directory `config.yaml`
4. Current directory `sample_config.yaml`

Create your configuration file based on the `sample_config.yaml` template:

```bash
# Create the mmrelay directory if it doesn't exist
mkdir -p ~/.mmrelay

# Copy the sample configuration
cp sample_config.yaml ~/.mmrelay/config.yaml

# Edit the configuration file
# Replace with your preferred editor
nano ~/.mmrelay/config.yaml
```

## Usage

Run the relay with the following command:

```bash
mmrelay
```

With command-line options:

```bash
mmrelay --config /path/to/config.yaml --logfile /path/to/logfile.log
```

### Command-Line Options

```
mmrelay [OPTIONS]

Options:
  --config PATH    Path to the configuration file
  --logfile PATH   Path to the log file
  --version        Show the version number and exit
  --help           Show this help message and exit
```

Example output:

```bash
INFO:meshtastic.matrix.relay:Starting Meshtastic <==> Matrix Relay...
INFO:meshtastic.matrix.relay:Connecting to radio at meshtastic.local ...
INFO:meshtastic.matrix.relay:Connected to radio at meshtastic.local.
INFO:meshtastic.matrix.relay:Listening for inbound radio messages ...
INFO:meshtastic.matrix.relay:Listening for inbound matrix messages ...
INFO:meshtastic.matrix.relay:Processing matrix message from @bob:matrix.org: Hi Alice!
INFO:meshtastic.matrix.relay:Sending radio message from Bob to radio broadcast
INFO:meshtastic.matrix.relay:Processing inbound radio message from !613501e4 on channel 0
INFO:meshtastic.matrix.relay:Relaying Meshtastic message from Alice to Matrix: [Alice/VeryCoolMeshnet]: Hey Bob!
INFO:meshtastic.matrix.relay:Sent inbound radio message to matrix room: #someroomid:example.matrix.org
```

## Running as a Service

### Systemd (Linux)

1. Create a systemd service file:
   ```bash
   mkdir -p ~/.config/systemd/user
   ```

2. Create the service file at `~/.config/systemd/user/mmrelay.service`:
   ```ini
   [Unit]
   Description=A Meshtastic <==> Matrix Relay
   After=default.target

   [Service]
   Type=idle
   ExecStart=/path/to/mmrelay --config %h/.mmrelay/config.yaml --logfile %h/.mmrelay/logs/mmrelay.log
   Restart=on-failure

   [Install]
   WantedBy=default.target
   ```

   Replace `/path/to/mmrelay` with the actual path (find it with `which mmrelay`).

3. Enable and start the service:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable mmrelay.service
   systemctl --user start mmrelay.service
   ```

4. Check the service status:
   ```bash
   systemctl --user status mmrelay.service
   ```

## Dockerized Versions (Unofficial)

If you would prefer to use a Dockerized version of the relay, there are unofficial third-party projects available. Please note that these are not officially supported, and issues should be reported to their respective repositories. For more details, visit the [Third Party Projects](https://github.com/geoffwhittington/meshtastic-matrix-relay/wiki/Third-Party-Projects) page.

## Development

### Contributing

Contributions are welcome! We use **Trunk** for automated code quality checks and formatting. The `trunk` launcher is committed directly to the repo, please run checks before submitting pull requests.

```bash
.trunk/trunk check --all --fix
```
