"""
Network and connection constants.

Contains timeout values, retry limits, connection types, and other
network-related configuration constants.
"""

# Connection types
CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_BLE = "ble"
CONNECTION_TYPE_NETWORK = (
    "network"  # DEPRECATED: Legacy alias for tcp, use CONNECTION_TYPE_TCP instead
)

# Configuration keys for connection settings
CONFIG_KEY_BLE_ADDRESS = "ble_address"
CONFIG_KEY_SERIAL_PORT = "serial_port"
CONFIG_KEY_HOST = "host"
CONFIG_KEY_CONNECTION_TYPE = "connection_type"

# Connection retry and timing
DEFAULT_BACKOFF_TIME = 10  # seconds
DEFAULT_RETRY_ATTEMPTS = 1
INFINITE_RETRIES = 0  # 0 means infinite retries
MINIMUM_MESSAGE_DELAY = 2.0  # Minimum delay for message queue fallback

# Error codes
ERRNO_BAD_FILE_DESCRIPTOR = 9

# System detection
SYSTEMD_INIT_SYSTEM = "systemd"

# Time conversion
MILLISECONDS_PER_SECOND = 1000
