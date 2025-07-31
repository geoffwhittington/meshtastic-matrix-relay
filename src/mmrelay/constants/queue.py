"""
Message queue constants.

Contains configuration values for the message queue system including
delays, size limits, and water marks for queue management.
"""

# Message timing constants
DEFAULT_MESSAGE_DELAY = 2.2  # Minimum delay in seconds (firmware constraint: >= 2.0)

# Queue size management
MAX_QUEUE_SIZE = 500
QUEUE_HIGH_WATER_MARK = 375  # 75% of MAX_QUEUE_SIZE
QUEUE_MEDIUM_WATER_MARK = 250  # 50% of MAX_QUEUE_SIZE

# Queue logging thresholds
QUEUE_LOG_THRESHOLD = 2  # Only log queue status when size >= this value
