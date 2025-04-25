"""
Meshtastic Matrix Relay - Bridge between Meshtastic mesh networks and Matrix chat rooms.
"""

import os

# Get version from environment variable if available (set by GitHub Actions)
# Otherwise, use a default version
__version__ = os.environ.get("GITHUB_REF_NAME", "1.0.1")
