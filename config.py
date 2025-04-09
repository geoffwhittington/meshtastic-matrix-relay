import os
import sys

import yaml
from yaml.loader import SafeLoader
import platformdirs

from cli import parse_arguments


def get_app_path():
    """
    Returns the base directory of the application, whether running from source or as an executable.
    """
    if getattr(sys, "frozen", False):
        # Running in a bundle (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # Running in a normal Python environment
        return os.path.dirname(os.path.abspath(__file__))


def get_config_paths():
    """
    Returns a list of possible config file paths in order of priority:
    1. Command line argument (if provided)
    2. Current directory
    3. User config directory (~/.config/mmrelay on Linux)
    4. Application directory
    """
    paths = []

    # Check command line arguments for config path
    args = parse_arguments()

    if args.config:
        paths.append(os.path.abspath(args.config))

    # Check current directory
    current_dir_config = os.path.join(os.getcwd(), "config.yaml")
    paths.append(current_dir_config)

    # Check user config directory
    user_config_dir = platformdirs.user_config_dir("mmrelay")
    user_config_path = os.path.join(user_config_dir, "config.yaml")
    paths.append(user_config_path)

    # Check application directory
    app_dir_config = os.path.join(get_app_path(), "config.yaml")
    paths.append(app_dir_config)

    return paths


def get_data_dir():
    """
    Returns the directory for storing application data files.
    Creates the directory if it doesn't exist.
    """
    data_dir = platformdirs.user_data_dir("mmrelay")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_log_dir():
    """
    Returns the directory for storing log files.
    Creates the directory if it doesn't exist.
    """
    log_dir = os.path.join(platformdirs.user_log_dir("mmrelay"))
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


relay_config = {}
config_paths = get_config_paths()
config_path = None

# Try each config path in order until we find one that exists
for path in config_paths:
    if os.path.isfile(path):
        config_path = path
        print(f"Loading configuration from: {config_path}")
        with open(config_path, "r") as f:
            relay_config = yaml.load(f, Loader=SafeLoader)
        break

if not config_path:
    print("Configuration file not found in any of the following locations:")
    for path in config_paths:
        print(f"  - {path}")
    print("Using empty configuration. This will likely cause errors.")
