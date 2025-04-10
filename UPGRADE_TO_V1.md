# Upgrading to MMRelay v1.0.0

This guide helps you migrate from previous versions to MMRelay v1.0.0. The new version brings significant improvements while maintaining compatibility with your existing setup.

> **New to MMRelay?** If you're installing for the first time, please see [INSTRUCTIONS.md](INSTRUCTIONS.md) instead.

## What's New in v1.0.0

### Major Improvements

- **PyPI Packaging**: Simple installation via `pip install mmrelay`
- **Standardized Directories**: Configuration, logs, and plugins in `~/.mmrelay/`
- **Enhanced CLI**: New command-line options and improved interface
- **Better Code Structure**: Modernized codebase with absolute imports
- **Full Compatibility**: Works with your existing configuration

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

# Install in development mode
pip install -e .
```

## Migration Steps

Follow these steps to migrate your existing setup:

### 1. Install the New Version

Use one of the upgrade options above to install MMRelay v1.0.0.

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

### 4. Update Your Service (If Using Systemd)

```bash
# Create the logs directory
mkdir -p ~/.mmrelay/logs

# Create a new service file with the correct paths
mkdir -p ~/.config/systemd/user
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

# Reload systemd and restart the service
systemctl --user daemon-reload
systemctl --user restart mmrelay.service
```

> **Note**: This creates a user-level systemd service. If you previously used a system-level service, you'll need to disable it first with `sudo systemctl disable mmrelay.service`.

## Configuration Changes

### New File Locations

MMRelay now uses standardized directories for all files:

| File Type | New Location | Notes |
|-----------|--------------|-------|
| Configuration | `~/.mmrelay/config.yaml` | Primary config file |
| Database | `~/.mmrelay/data/meshtastic.sqlite` | Automatically migrated |
| Logs | `~/.mmrelay/logs/mmrelay.log` | Configurable with `--logfile` |
| Custom Plugins | `~/.mmrelay/plugins/custom/` | Your own plugins |
| Community Plugins | `~/.mmrelay/plugins/community/` | Third-party plugins |

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

### Backward Compatibility

Your existing configuration will continue to work without changes. The application will automatically:

- Find your existing config file
- Migrate your database if needed
- Support legacy configuration options
- Load plugins from both old and new locations

## Command-Line Interface

MMRelay v1.0.0 includes an improved command-line interface:

```
mmrelay [OPTIONS]

Options:
  --config PATH    Path to the configuration file
  --logfile PATH   Path to the log file
  --version        Show the version number and exit
  --help           Show help message and exit
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Configuration not found | Use `--config` to specify the path |
| Missing dependencies | Run `pip install -r requirements.txt` |
| Service won't start | Check paths in the service file |
| Plugin errors | Ensure plugins are in the correct location |

### Diagnostic Steps

1. **Check the logs**: Look at `~/.mmrelay/logs/mmrelay.log` for error messages
2. **Verify configuration**: Ensure your config file is valid YAML
3. **Run with verbose output**: Use `mmrelay --config ~/.mmrelay/config.yaml` to see startup messages
4. **Check permissions**: Ensure the application has access to all required directories

### Getting Help

- Join our Matrix room: [#mmrelay:meshnet.club](https://matrix.to/#/#mmrelay:meshnet.club)
- Open an issue on GitHub: [meshtastic-matrix-relay](https://github.com/geoffwhittington/meshtastic-matrix-relay/issues)
- Check the wiki for additional documentation
