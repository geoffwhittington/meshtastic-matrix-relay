"""
Network and connection constants.

Contains timeout values, retry limits, connection types, and other
network-related configuration constants.
"""

# Connection types
CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_BLE = "ble"
CONNECTION_TYPE_NETWORK = "network"  # Legacy alias for tcp

# Connection retry and timing
DEFAULT_BACKOFF_TIME = 10  # seconds
DEFAULT_RETRY_ATTEMPTS = 1

# Error codes
ERRNO_BAD_FILE_DESCRIPTOR = 9

# System detection
SYSTEMD_INIT_SYSTEM = "systemd"
