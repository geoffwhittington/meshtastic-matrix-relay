"""
Database-related constants.

Contains default values for database configuration, message retention,
and data management settings.
"""

# Message retention defaults
DEFAULT_MSGS_TO_KEEP = 500
DEFAULT_MAX_DATA_ROWS_PER_NODE = 50

# Database operation defaults
DEFAULT_QUEUE_LIMIT = 100  # Reduced from 500 for better performance
