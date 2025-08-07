# MMRelay Documentation

Welcome to the MMRelay documentation! This directory contains comprehensive guides for setting up and using MMRelay.

## Getting Started

- **[Installation Guide](INSTRUCTIONS.md)** - Complete setup instructions for MMRelay v1.2+
- **[E2EE Guide](E2EE.md)** - Matrix End-to-End Encryption setup and usage
- **[Docker Guide](DOCKER.md)** - Docker deployment and configuration

## Advanced Configuration

- **[Extra Configuration](EXTRA_CONFIGURATION.md)** - Advanced features like message prefixes, debug logging, and plugins
- **[Constants Reference](CONSTANTS.md)** - Configuration constants and values

## Quick Reference

### New in v1.2
- **Full Matrix E2EE Support** - Secure communication in encrypted rooms
- **`--auth` Command** - Simplified authentication setup
- **Automatic Encryption** - Seamless handling of encrypted/unencrypted rooms

### Essential Commands

```bash
# Generate configuration file
mmrelay --generate-config

# Set up Matrix authentication (recommended)
mmrelay --auth

# Validate configuration
mmrelay --check-config

# Start MMRelay
mmrelay
```

### File Locations

| File | Purpose | Location |
|------|---------|----------|
| Configuration | Main settings | `~/.mmrelay/config.yaml` |
| Credentials | Matrix authentication | `~/.mmrelay/credentials.json` |
| E2EE Store | Encryption keys | `~/.mmrelay/store/` |
| Logs | Application logs | `~/.mmrelay/logs/` |

## Documentation Structure

```
docs/
├── README.md              # This file - documentation index
├── INSTRUCTIONS.md        # Main installation and setup guide
├── E2EE.md               # End-to-End Encryption guide
├── DOCKER.md             # Docker deployment guide
├── EXTRA_CONFIGURATION.md # Advanced configuration options
├── CONSTANTS.md          # Configuration constants reference
└── dev/                  # Developer documentation
    └── E2EE_IMPLEMENTATION_NOTES.md  # Technical implementation details
```

## Getting Help

1. **Check the relevant guide** for your specific use case
2. **Review troubleshooting sections** in each guide
3. **Validate your configuration** with `mmrelay --check-config`
4. **Enable debug logging** for detailed diagnostics
5. **Ask for help** in the MMRelay Matrix room with your configuration and log excerpts

## Version Information

- **Current Version**: v1.2+
- **Python Requirement**: 3.9+
- **Supported Platforms**: Linux, macOS, Windows
- **Key Features**: Meshtastic ↔ Matrix relay, E2EE support, Docker deployment, Plugin system
