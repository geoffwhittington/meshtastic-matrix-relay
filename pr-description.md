# Component Debug Logging and Configurable Health Checks

This PR adds two new features to improve debugging capabilities and connection monitoring flexibility.

## New Features

### Component-Specific Debug Logging

Enable debug logging for specific external libraries to help with troubleshooting:

```yaml
logging:
  debug:
    matrix_nio: false # Matrix client debugging
    bleak: false # BLE debugging
    meshtastic: false # Meshtastic library debugging
```

**Benefits:**

- Targeted debugging without flooding logs
- Easier troubleshooting of Matrix, BLE, or Meshtastic issues
- Clean, maintainable implementation

### Configurable Health Check Options

Customize connection monitoring behavior:

```yaml
meshtastic:
  health_check:
    enabled: true # Enable/disable health checks (default: true)
    heartbeat_interval: 60 # Interval in seconds (default: 60)
```

**Benefits:**

- Disable health checks when not needed to reduce network traffic
- Configurable intervals for different network conditions
- Backward compatible with existing configurations
- Improved connection stability with 60-second default (was 30)

## Technical Details

- Comprehensive documentation included
- All code review feedback addressed (Gemini + CodeRabbit)
- Follows Python best practices with module-level constants
- Proper initialization order for debug logging
- All code quality checks pass

Both features are designed to be refined based on user feedback.
