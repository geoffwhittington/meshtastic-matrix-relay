"""
Command-line interface handling for the Meshtastic Matrix Relay.
"""

import argparse

# Import version from package
from mmrelay import __version__


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: The parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="Meshtastic Matrix Relay - Bridge between Meshtastic and Matrix"
    )
    parser.add_argument("--config", help="Path to config file", default=None)
    parser.add_argument("--logfile", help="Path to log file", default=None)
    parser.add_argument("--version", action="version", version=f"mmrelay {__version__}")
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate a sample config.yaml file",
    )

    return parser.parse_args()


def get_version():
    """
    Returns the current version of the application.

    Returns:
        str: The version string
    """
    return __version__
