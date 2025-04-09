# Upgrading to mmrelay v1.0.0

This guide provides instructions for upgrading to mmrelay v1.0.0 from previous versions. Version 1.0.0 introduces several improvements including PyPI packaging, standardized configuration locations, and better CLI support.

## What's New in v1.0.0

- **PyPI Packaging**: mmrelay is now available on PyPI for easier installation
- **Standardized Configuration**: Uses platformdirs for standard config locations
- **Improved CLI**: Enhanced command-line interface with more options
- **Absolute Imports**: Code structure improved with absolute imports
- **Backward Compatibility**: Maintains compatibility with existing configurations

## Upgrade Instructions

### Method 1: Install from PyPI (Recommended)

```bash
# Install using pip
pip install mmrelay

# Or use pipx for isolated installation (recommended)
pipx install mmrelay
```

### Method 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
cd meshtastic-matrix-relay

# Install using pip
pip install -e .

# Or use pipx for isolated installation (recommended)
pipx install -e .
```

## Configuration Changes

The application now looks for configuration files in the following locations (in order):

1. Path specified with `--config` command-line option
2. `~/.mmrelay/config.yaml`
3. Current directory `config.yaml`
4. Current directory `sample_config.yaml`

### Migrating Your Configuration

If you're upgrading from a previous version, your configuration will continue to work as before. However, we recommend moving your configuration to the new standard location:

```bash
# Create the mmrelay directory if it doesn't exist
mkdir -p ~/.mmrelay

# Copy your existing configuration
cp config.yaml ~/.mmrelay/config.yaml
```

## Database Location

The SQLite database is now stored in `~/.mmrelay/data/meshtastic.sqlite` by default. Existing databases will be automatically migrated if found in the previous location.

## Log Files

Log files are now stored in `~/.mmrelay/logs/` by default. You can specify a custom log file location using the `--logfile` option.

## Plugins

Core plugins remain in their original location within the package. Custom and community plugins should be placed in:

- Custom plugins: `~/.mmrelay/plugins/custom/`
- Community plugins: `~/.mmrelay/plugins/community/`

The application will check these locations as well as the current directory for backward compatibility.

## Running as a Service

### Systemd (Linux)

Create a systemd service file at `~/.config/systemd/user/mmrelay.service`:

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

Then enable and start the service:

```bash
systemctl --user daemon-reload
systemctl --user enable mmrelay.service
systemctl --user start mmrelay.service
```

## Command-Line Options

The application now supports the following command-line options:

- `--config PATH`: Specify the configuration file path
- `--logfile PATH`: Specify the log file path
- `--version`: Show the version number and exit
- `--help`: Show help message and exit

## Troubleshooting

If you encounter any issues after upgrading:

1. Check the log file for error messages
2. Verify your configuration file is correctly formatted
3. Ensure all dependencies are installed
4. Try running with the `--config` option pointing to your configuration file

For more help, please open an issue on the GitHub repository.
