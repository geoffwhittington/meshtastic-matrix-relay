# MMRelay v1.1.2 Release Notes

## New Features

### 🔍 Component-Specific Debug Logging

Enable targeted debug logging for specific external libraries to help with troubleshooting:

- **Matrix Client**: Debug matrix-nio library for Matrix connection issues
- **BLE Connections**: Debug bleak library for Bluetooth Low Energy problems
- **Meshtastic Library**: Debug meshtastic library for device communication issues

Configure in your `config.yaml`:

```yaml
logging:
  debug:
    matrix_nio: false # Matrix client debugging
    bleak: false # BLE debugging
    meshtastic: false # Meshtastic library debugging
```

### ⚙️ Configurable Health Check Options

Customize connection monitoring behavior for different environments:

- **Enable/Disable**: Turn health checks on or off completely
- **Custom Intervals**: Configure heartbeat timing (default now 60 seconds)
- **Backward Compatible**: Existing configurations continue to work

Configure in your `config.yaml`:

```yaml
meshtastic:
  health_check:
    enabled: true # Enable/disable health checks (default: true)
    heartbeat_interval: 60 # Interval in seconds (default: 60)
```

## Improvements

### 🔧 Better Connection Stability

- **Increased Default Health Check Interval**: Changed from 30 to 60 seconds to reduce frequent reconnections
- **Improved Configuration Organization**: Health check options moved to bottom of meshtastic section for better user experience

### 🛠️ Code Quality Enhancements

- **Python Best Practices**: Module-level constants and proper code organization
- **Proper Initialization**: Fixed component debug logging initialization order
- **Comprehensive Documentation**: Added detailed docs for new features

## Bug Fixes

### 🐛 Fixed Issues

- **Component Debug Logging**: Fixed initialization order issue where config wasn't available when debug logging was configured
- **Health Check Timing**: Resolved frequent reconnection issues caused by aggressive 30-second health checks

## Technical Details

- All code review feedback addressed (Gemini + CodeRabbit AI)
- Comprehensive test coverage and documentation
- Backward compatibility maintained
- Clean, maintainable code following Python conventions

## Getting Help

For questions about these new features, visit the [MMRelay Matrix room](https://matrix.to/#/#mmrelay:meshnet.club) for community support and testing assistance.

---

**Note**: These features are subject to refinement based on user feedback. Please report any issues or suggestions!
