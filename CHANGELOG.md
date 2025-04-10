# Changelog for mmrelay v1.0.0

## What's New in v1.0.0

### Major Features
- **PyPI Packaging**: mmrelay is now available on PyPI for easier installation
- **Standardized Configuration**: Uses platformdirs for standard config locations
- **Improved CLI**: Enhanced command-line interface with more options
- **Absolute Imports**: Code structure improved with absolute imports
- **Backward Compatibility**: Maintains compatibility with existing configurations

### Installation Improvements
- Added support for installation via pip and pipx
- Created proper Python package structure with setup.cfg and pyproject.toml
- Implemented entry points for command-line usage
- Added version information accessible via `mmrelay --version`

### Configuration Enhancements
- Configuration files now follow XDG standards using platformdirs
- Standard configuration location at ~/.mmrelay/config.yaml
- Improved configuration file search logic
- Added command-line options for specifying config and log file locations

### File Management
- Database files stored in ~/.mmrelay/data/
- Log files stored in ~/.mmrelay/logs/
- Custom and community plugins stored in ~/.mmrelay/plugins/

### Documentation
- Added comprehensive upgrade guide (UPGRADE_TO_V1.md)
- Updated installation instructions
- Added systemd service setup instructions

### Code Quality
- Refactored code to use absolute imports
- Improved module organization
- Enhanced error handling and logging

## Contributors
- @jeremiah-k
- @geoffwhittington

## Full Changelog
For a detailed list of all changes, see the [commit history](https://github.com/geoffwhittington/meshtastic-matrix-relay/compare/0.10.1...v1.0.0).
