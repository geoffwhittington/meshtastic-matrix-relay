"""
User-facing messages and string templates.

Contains error messages, log templates, command responses, and other
strings that are displayed to users or logged.
"""

# Log configuration defaults
DEFAULT_LOG_SIZE_MB = 5
DEFAULT_LOG_BACKUP_COUNT = 1
LOG_SIZE_BYTES_MULTIPLIER = 1024 * 1024  # Convert MB to bytes

# Component logger names
COMPONENT_LOGGERS = {
    "matrix_nio": ["nio", "nio.client", "nio.http", "nio.crypto"],
    "bleak": ["bleak", "bleak.backends"],
    "meshtastic": [
        "meshtastic",
        "meshtastic.serial_interface", 
        "meshtastic.tcp_interface",
        "meshtastic.ble_interface",
    ],
}

# Log level styling
LOG_LEVEL_STYLES = {
    "DEBUG": {"color": "cyan"},
    "INFO": {"color": "green"},
    "WARNING": {"color": "yellow"},
    "ERROR": {"color": "red"},
    "CRITICAL": {"color": "red", "bold": True},
}
