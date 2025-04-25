"""
Meshtastic Matrix Relay - Bridge between Meshtastic mesh networks and Matrix chat rooms.
"""

import importlib.metadata
import os

# Try to get version from package metadata (setup.cfg)
try:
    __version__ = importlib.metadata.version("mmrelay")
except importlib.metadata.PackageNotFoundError:
    # If package is not installed, fall back to environment variable or default
    __version__ = os.environ.get("GITHUB_REF_NAME", "1.0.1")
