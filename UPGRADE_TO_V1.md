# Upgrading to MMRelay v1.0

This guide helps you migrate from previous versions to MMRelay v1.0. The new version brings significant improvements while maintaining compatibility with your existing setup.

> **New to MMRelay?** If you're installing for the first time, please see [INSTRUCTIONS.md](INSTRUCTIONS.md) instead.

## What's New in v1.0

### Major Improvements

- **PyPI Packaging**: Simple installation via `pip install mmrelay`
- **Standardized Directories**: Configuration, logs, and plugins in `~/.mmrelay/`
- **Enhanced CLI**: New command-line options and improved interface
- **Better Code Structure**: Modernized codebase with absolute imports
- **Full Compatibility**: Works with your existing configuration

### Enhanced Command-Line Options

MMRelay v1.0 includes new command-line options for better flexibility:

```bash
# Specify a custom data directory
mmrelay --data-dir /path/to/data/directory

# Set a specific log level for debugging
mmrelay --log-level debug

# Generate a sample configuration file
mmrelay --generate-config

# Check if your configuration is valid
mmrelay --check-config
```

See `mmrelay --help` for all available options.

## Upgrade Options

### Option 1: Quick Upgrade (Recommended)

Install directly from PyPI:

```bash
# Install using pip
pip install mmrelay

# Or use pipx for isolated installation (recommended)
pipx install mmrelay
```

### Option 2: Developer Upgrade

If you want to contribute or modify the code:

```bash
# Clone the repository (or pull latest changes)
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
cd meshtastic-matrix-relay

# Install in editable mode for development
pipx install -e .
```

## Migration Steps

Follow these steps to migrate your existing setup:

### 1. Install the New Version

Use one of the upgrade options above to install MMRelay v1.0.

### 2. Move Your Configuration

```bash
# Create the standard config directory
mkdir -p ~/.mmrelay

# Copy your existing configuration to the new location
cp config.yaml ~/.mmrelay/config.yaml
```

> **Note**: Your original config.yaml will remain in place for backward compatibility. MMRelay will check both locations, but the ~/.mmrelay version will take precedence if both exist. See the "Configuration Search Path" section below for details.

### 3. Migrate Custom Plugins (If Any)

```bash
# Create the plugins directory
mkdir -p ~/.mmrelay/plugins/custom

# Copy your custom plugins (if you have any)
cp plugins/custom/* ~/.mmrelay/plugins/custom/ 2>/dev/null || echo "No custom plugins found to migrate"
```

> **Note**: MMRelay will check both the old and new plugin locations, but plugins in the new location will take precedence if duplicates exist.

### 4. Set Up the Service (Optional)

MMRelay includes a built-in command to install a systemd user service:

```bash
# Install or update the service
mmrelay --install-service
```

This command will:

- Create the necessary directories
- Install or update the service file
- Ask if you want to enable and start the service
- Show you commands for controlling the service

#### Service Control Commands

Once installed, you can control the service with these commands:

```bash
# Start the service
systemctl --user start mmrelay.service

# Stop the service
systemctl --user stop mmrelay.service

# Restart the service
systemctl --user restart mmrelay.service

# Check service status
systemctl --user status mmrelay.service

# Enable service to start at boot
systemctl --user enable mmrelay.service

# View service logs
journalctl --user -u mmrelay.service

# Or watch the application log file in real-time
tail -f ~/.mmrelay/logs/mmrelay.log
```

#### Run Without a Service

You can also run MMRelay manually without a service:

```bash
mmrelay --config ~/.mmrelay/config.yaml
```

> **Note**: If you previously used a system-level service, you'll need to disable it first with `sudo systemctl disable mmrelay.service`.

## Configuration Changes

### New File Locations

MMRelay now uses standardized directories for all files:

| File Type         | New Location                        | Notes                         |
| ----------------- | ----------------------------------- | ----------------------------- |
| Configuration     | `~/.mmrelay/config.yaml`            | Primary config file           |
| Database          | `~/.mmrelay/data/meshtastic.sqlite` | Automatically migrated        |
| Logs              | `~/.mmrelay/logs/mmrelay.log`       | Configurable with `--logfile` |
| Custom Plugins    | `~/.mmrelay/plugins/custom/`        | Your own plugins              |
| Community Plugins | `~/.mmrelay/plugins/community/`     | Third-party plugins           |

### Configuration Search Path

The application looks for configuration in this order:

1. Path specified with `--config` command-line option
2. `~/.mmrelay/config.yaml` (recommended location)
3. Current directory `config.yaml` (for backward compatibility)
4. Current directory `sample_config.yaml` (fallback)

### Configuration Format Changes

Some configuration options have been renamed for clarity:

- `db:` → `database:` (old option still works but will show a deprecation notice)
- `network` connection mode → `tcp` (both options supported for compatibility)

For a complete list of deprecated options and breaking changes, please see [ANNOUNCEMENT.md](ANNOUNCEMENT.md).

### Backward Compatibility

Your existing configuration will continue to work without changes. The application will automatically:

- Find your existing config file
- Migrate your database if needed
- Support legacy configuration options
- Load plugins from both old and new locations

## Troubleshooting

### Common Issues

| Issue                   | Solution                                                      |
| ----------------------- | ------------------------------------------------------------- |
| Configuration not found | Use `--config` to specify the path                            |
| Missing dependencies    | Run `pip install -r requirements.txt`                         |
| Service won't start     | Run `systemctl --user status mmrelay.service` to check status |
| Plugin errors           | Ensure plugins are in the correct location                    |

### Diagnostic Steps

1. **Check the logs**: Look at `~/.mmrelay/logs/mmrelay.log` for error messages
2. **Verify configuration**: Ensure your config file is valid YAML
3. **Run with verbose output**: Use `mmrelay --config ~/.mmrelay/config.yaml` to see startup messages
4. **Check permissions**: Ensure the application has access to all required directories

### Getting Help

- Join our Matrix room: [#mmrelay:meshnet.club](https://matrix.to/#/#mmrelay:meshnet.club)
- Open an issue on GitHub: [meshtastic-matrix-relay](https://github.com/geoffwhittington/meshtastic-matrix-relay/issues)
- Check the wiki for additional documentation
