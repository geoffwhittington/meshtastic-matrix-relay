import logging
import os
import sys

import platformdirs
import yaml
from yaml.loader import SafeLoader

from mmrelay.cli import parse_arguments

# Define custom base directory for Unix systems
APP_NAME = "mmrelay"
APP_AUTHOR = None  # No author directory


# Custom base directory for Unix systems
def get_base_dir():
    """Returns the base directory for all application files."""
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay for Linux and Mac
        return os.path.expanduser(os.path.join("~", "." + APP_NAME))
    else:
        # Use platformdirs default for Windows
        return platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)


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
    2. User config directory (~/.mmrelay/config/ on Linux)
    3. Current directory (for backward compatibility)
    4. Application directory (for backward compatibility)
    """
    paths = []

    # Check command line arguments for config path
    args = parse_arguments()

    if args.config:
        paths.append(os.path.abspath(args.config))

    # Check user config directory (preferred location)
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay/ for Linux and Mac
        user_config_dir = get_base_dir()
    else:
        # Use platformdirs default for Windows
        user_config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)

    os.makedirs(user_config_dir, exist_ok=True)
    user_config_path = os.path.join(user_config_dir, "config.yaml")
    paths.append(user_config_path)

    # Check current directory (for backward compatibility)
    current_dir_config = os.path.join(os.getcwd(), "config.yaml")
    paths.append(current_dir_config)

    # Check application directory (for backward compatibility)
    app_dir_config = os.path.join(get_app_path(), "config.yaml")
    paths.append(app_dir_config)

    return paths


def get_data_dir():
    """
    Returns the directory for storing application data files.
    Creates the directory if it doesn't exist.
    """
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay/data/ for Linux and Mac
        data_dir = os.path.join(get_base_dir(), "data")
    else:
        # Use platformdirs default for Windows
        data_dir = platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_log_dir():
    """
    Returns the directory for storing log files.
    Creates the directory if it doesn't exist.
    """
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay/logs/ for Linux and Mac
        log_dir = os.path.join(get_base_dir(), "logs")
    else:
        # Use platformdirs default for Windows
        log_dir = platformdirs.user_log_dir(APP_NAME, APP_AUTHOR)

    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# Set up a basic logger for config
logger = logging.getLogger("Config")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %z",
    )
)
logger.addHandler(handler)

# Initialize empty config
relay_config = {}
config_path = None


def load_config(config_file=None):
    """Load the configuration from the specified file or search for it.

    Args:
        config_file (str, optional): Path to the config file. If None, search for it.

    Returns:
        dict: The loaded configuration
    """
    global relay_config, config_path

    # If a specific config file was provided, use it
    if config_file and os.path.isfile(config_file):
        logger.info(f"Loading configuration from: {config_file}")
        with open(config_file, "r") as f:
            relay_config = yaml.load(f, Loader=SafeLoader)
        config_path = config_file
        return relay_config

    # Otherwise, search for a config file
    config_paths = get_config_paths()

    # Try each config path in order until we find one that exists
    for path in config_paths:
        if os.path.isfile(path):
            config_path = path
            logger.info(f"Loading configuration from: {config_path}")
            with open(config_path, "r") as f:
                relay_config = yaml.load(f, Loader=SafeLoader)
            return relay_config

    # No config file found
    logger.error("Configuration file not found in any of the following locations:")
    for path in config_paths:
        logger.error(f"  - {path}")
    logger.error("Using empty configuration. This will likely cause errors.")
    logger.error(
        "Run 'mmrelay --generate-config' to generate a sample configuration file."
    )

    return relay_config
