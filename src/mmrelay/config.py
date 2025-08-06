import json
import logging
import os
import sys

import platformdirs
import yaml
from yaml.loader import SafeLoader

# Import application constants
from mmrelay.constants.app import APP_AUTHOR, APP_NAME
from mmrelay.constants.config import (
    CONFIG_KEY_ACCESS_TOKEN,
    CONFIG_KEY_BOT_USER_ID,
    CONFIG_KEY_HOMESERVER,
    CONFIG_SECTION_MATRIX,
)

# Global variable to store the custom data directory
custom_data_dir = None


# Custom base directory for Unix systems
def get_base_dir():
    """Returns the base directory for all application files.

    If a custom data directory has been set via --data-dir, that will be used.
    Otherwise, defaults to ~/.mmrelay on Unix systems or the appropriate
    platformdirs location on Windows.
    """
    # If a custom data directory has been set, use that
    if custom_data_dir:
        return custom_data_dir

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


def get_config_paths(args=None):
    """
    Return a prioritized list of possible configuration file paths for the application.

    The search order is: a command-line specified path (if provided), the user config directory, the current working directory, and the application directory. The user config directory is skipped if it cannot be created due to permission or OS errors.

    Parameters:
        args: Parsed command-line arguments, expected to have a 'config' attribute specifying a config file path.

    Returns:
        List of absolute paths to candidate configuration files, ordered by priority.
    """
    paths = []

    # Check command line arguments for config path
    if args and args.config:
        paths.append(os.path.abspath(args.config))

    # Check user config directory (preferred location)
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay/ for Linux and Mac
        user_config_dir = get_base_dir()
    else:
        # Use platformdirs default for Windows
        user_config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)

    try:
        os.makedirs(user_config_dir, exist_ok=True)
        user_config_path = os.path.join(user_config_dir, "config.yaml")
        paths.append(user_config_path)
    except (OSError, PermissionError):
        # If we can't create the user config directory, skip it
        pass

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


def get_plugin_data_dir(plugin_name=None):
    """
    Returns the directory for storing plugin-specific data files.
    If plugin_name is provided, returns a plugin-specific subdirectory.
    Creates the directory if it doesn't exist.

    Example:
    - get_plugin_data_dir() returns ~/.mmrelay/data/plugins/
    - get_plugin_data_dir("my_plugin") returns ~/.mmrelay/data/plugins/my_plugin/
    """
    # Get the base data directory
    base_data_dir = get_data_dir()

    # Create the plugins directory
    plugins_data_dir = os.path.join(base_data_dir, "plugins")
    os.makedirs(plugins_data_dir, exist_ok=True)

    # If a plugin name is provided, create and return a plugin-specific directory
    if plugin_name:
        plugin_data_dir = os.path.join(plugins_data_dir, plugin_name)
        os.makedirs(plugin_data_dir, exist_ok=True)
        return plugin_data_dir

    return plugins_data_dir


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


def get_e2ee_store_dir():
    """
    Returns the directory for storing E2EE data (encryption keys, etc.).
    Creates the directory if it doesn't exist.
    """
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay/store/ for Linux and Mac
        store_dir = os.path.join(get_base_dir(), "store")
    else:
        # Use platformdirs default for Windows
        store_dir = os.path.join(
            platformdirs.user_data_dir(APP_NAME, APP_AUTHOR), "store"
        )

    os.makedirs(store_dir, exist_ok=True)
    return store_dir


def load_credentials():
    """
    Load Matrix credentials from credentials.json file.

    Returns:
        dict or None: Credentials dictionary if file exists and is valid, None otherwise.
    """
    try:
        config_dir = get_base_dir()
        credentials_path = os.path.join(config_dir, "credentials.json")

        if os.path.exists(credentials_path):
            with open(credentials_path, "r") as f:
                credentials = json.load(f)

            # Validate required fields
            required_fields = ["homeserver", "user_id", "access_token", "device_id"]
            if all(field in credentials for field in required_fields):
                return credentials
            else:
                logger.warning(f"credentials.json missing required fields: {required_fields}")
                return None
        else:
            return None
    except (json.JSONDecodeError, OSError, PermissionError) as e:
        logger.warning(f"Error loading credentials.json: {e}")
        return None


def save_credentials(credentials):
    """
    Save Matrix credentials to credentials.json file.

    Args:
        credentials (dict): Credentials dictionary to save.
    """
    try:
        config_dir = get_base_dir()
        credentials_path = os.path.join(config_dir, "credentials.json")

        with open(credentials_path, "w") as f:
            json.dump(credentials, f, indent=2)

        logger.info(f"Saved credentials to {credentials_path}")
    except (OSError, PermissionError) as e:
        logger.error(f"Error saving credentials.json: {e}")


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


def set_config(module, passed_config):
    """
    Assigns the provided configuration dictionary to a module and sets additional attributes for known module types.

    For modules named "matrix_utils" or "meshtastic_utils", sets specific configuration attributes if present. Calls the module's `setup_config()` method if it exists for backward compatibility.

    Returns:
        dict: The configuration dictionary that was assigned to the module.
    """
    # Set the module's config variable
    module.config = passed_config

    # Handle module-specific setup based on module name
    module_name = module.__name__.split(".")[-1]

    if module_name == "matrix_utils":
        # Set Matrix-specific configuration
        if (
            hasattr(module, "matrix_homeserver")
            and CONFIG_SECTION_MATRIX in passed_config
        ):
            module.matrix_homeserver = passed_config[CONFIG_SECTION_MATRIX][
                CONFIG_KEY_HOMESERVER
            ]
            module.matrix_rooms = passed_config["matrix_rooms"]
            module.matrix_access_token = passed_config[CONFIG_SECTION_MATRIX][
                CONFIG_KEY_ACCESS_TOKEN
            ]
            module.bot_user_id = passed_config[CONFIG_SECTION_MATRIX][
                CONFIG_KEY_BOT_USER_ID
            ]

    elif module_name == "meshtastic_utils":
        # Set Meshtastic-specific configuration
        if hasattr(module, "matrix_rooms") and "matrix_rooms" in passed_config:
            module.matrix_rooms = passed_config["matrix_rooms"]

    # If the module still has a setup_config function, call it for backward compatibility
    if hasattr(module, "setup_config") and callable(module.setup_config):
        module.setup_config()

    return passed_config


def load_config(config_file=None, args=None):
    """
    Load the application configuration from a specified file or by searching standard locations.

    If a config file path is provided and valid, attempts to load and parse it as YAML. If not, searches for a configuration file in prioritized locations and loads the first valid one found. Returns an empty dictionary if no valid configuration is found or if loading fails due to file or YAML errors.

    Parameters:
        config_file (str, optional): Path to a specific configuration file. If None, searches default locations.
        args: Parsed command-line arguments, used to determine config search order.

    Returns:
        dict: The loaded configuration dictionary, or an empty dictionary if loading fails.
    """
    global relay_config, config_path

    # If a specific config file was provided, use it
    if config_file and os.path.isfile(config_file):
        # Store the config path but don't log it yet - will be logged by main.py
        try:
            with open(config_file, "r") as f:
                relay_config = yaml.load(f, Loader=SafeLoader)
            config_path = config_file
            return relay_config
        except (yaml.YAMLError, PermissionError, OSError) as e:
            logger.error(f"Error loading config file {config_file}: {e}")
            return {}

    # Otherwise, search for a config file
    config_paths = get_config_paths(args)

    # Try each config path in order until we find one that exists
    for path in config_paths:
        if os.path.isfile(path):
            config_path = path
            # Store the config path but don't log it yet - will be logged by main.py
            try:
                with open(config_path, "r") as f:
                    relay_config = yaml.load(f, Loader=SafeLoader)
                return relay_config
            except (yaml.YAMLError, PermissionError, OSError) as e:
                logger.error(f"Error loading config file {path}: {e}")
                continue  # Try the next config path

    # No config file found
    logger.error("Configuration file not found in any of the following locations:")
    for path in config_paths:
        logger.error(f"  - {path}")
    logger.error("Using empty configuration. This will likely cause errors.")
    logger.error(
        "Run 'mmrelay --generate-config' to generate a sample configuration file."
    )

    return relay_config
