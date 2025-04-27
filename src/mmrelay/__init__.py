"""
Meshtastic Matrix Relay - Bridge between Meshtastic mesh networks and Matrix chat rooms.
"""

import os

import pkg_resources

# First try to get version from setup.cfg metadata using pkg_resources
try:
    __version__ = pkg_resources.get_distribution("mmrelay").version
except pkg_resources.DistributionNotFound:
    # Fall back to environment variable (GitHub tag) if available
    if "GITHUB_REF_NAME" in os.environ:
        __version__ = os.environ.get("GITHUB_REF_NAME")
    else:
        # If all else fails, use hardcoded version
        __version__ = "1.0.4"
