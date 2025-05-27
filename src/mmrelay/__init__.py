"""
Meshtastic Matrix Relay - Bridge between Meshtastic mesh networks and Matrix chat rooms.
"""

import os

import pkg_resources

# First try to get version from environment variable (GitHub tag)
if "GITHUB_REF_NAME" in os.environ:
    __version__ = os.environ.get("GITHUB_REF_NAME")
else:
    # Fall back to setup.cfg metadata using pkg_resources (compatible with PyInstaller)
    try:
        __version__ = pkg_resources.get_distribution("mmrelay").version
    except pkg_resources.DistributionNotFound:
        # If all else fails, use hardcoded version
        __version__ = "1.0.8"
