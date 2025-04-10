# MMRelay v1.0.0 Released 🔖

We're pleased to announce MMRelay v1.0.0, our first stable major release since the project's inception in April 2023. This version marks a significant milestone, reflecting steady improvements driven by our contributors and users.

## Special Thanks

We sincerely thank everyone who contributed code, provided feedback, or helped test MMRelay. Your efforts have directly shaped this release.

## What's New in v1.0.0

- **PyPI Release**: Quickly install via `pip` or `pipx`
- **Standardized Configuration**: Uses `platformdirs` for consistent configuration paths
- **Enhanced CLI**: Improved command-line experience and new options
- **Absolute Imports**: Clearer, more maintainable codebase
- **Configuration Improvements**:
  - Standard locations for config files, logs, and plugins
  - Backward compatible with existing setups
  - Clear migration path for legacy configurations

### Important Changes

Some configuration options have been renamed for clarity:
- `db:` → `database:` (old option still works but will show a deprecation notice)
- `network` connection mode → `tcp` (both options supported for compatibility)

## Need More Time?

**Not ready to upgrade yet?** No problem!

If you've pulled the latest changes but need more time to prepare for the upgrade, you can continue using the previous release:

```bash
# Switch back to the previous stable release
git checkout 0.10.1
```

## Resources

### For New Users
- **Quick Start**: `pip install mmrelay` or `pipx install mmrelay`
- **Installation Guide**: [INSTRUCTIONS.md](https://github.com/geoffwhittington/meshtastic-matrix-relay/blob/main/INSTRUCTIONS.md)
- **Configuration Template**: [sample_config.yaml](https://github.com/geoffwhittington/meshtastic-matrix-relay/blob/main/sample_config.yaml)

### For Existing Users
- **Upgrade Guide**: [UPGRADE_TO_V1.md](https://github.com/geoffwhittington/meshtastic-matrix-relay/blob/main/UPGRADE_TO_V1.md) - Step-by-step migration instructions
- **Configuration Changes**: See the [sample_config.yaml](https://github.com/geoffwhittington/meshtastic-matrix-relay/blob/main/sample_config.yaml) for examples of the new format

## Join the Conversation

Matrix chat rooms:
- Project discussion: [#mmrelay:meshnet.club](https://matrix.to/#/#mmrelay:meshnet.club)
- Relay support: [#relay-room:meshnet.club](https://matrix.to/#/#relay-room:meshnet.club)

Thanks for your support,
— MMRelay Team
