# trunk-ignore-all(bandit)
import hashlib
import importlib.util
import os
import subprocess
import sys

from mmrelay.config import get_app_path, get_base_dir
from mmrelay.log_utils import get_logger

# Global config variable that will be set from main.py
config = None

logger = get_logger(name="Plugins")
sorted_active_plugins = []
plugins_loaded = False


def get_custom_plugin_dirs():
    """
    Returns a list of directories to check for custom plugins in order of priority:
    1. User directory (~/.mmrelay/plugins/custom)
    2. Local directory (plugins/custom) for backward compatibility
    """
    dirs = []

    # Check user directory first (preferred location)
    user_dir = os.path.join(get_base_dir(), "plugins", "custom")
    os.makedirs(user_dir, exist_ok=True)
    dirs.append(user_dir)

    # Check local directory (backward compatibility)
    local_dir = os.path.join(get_app_path(), "plugins", "custom")
    dirs.append(local_dir)

    return dirs


def get_community_plugin_dirs():
    """
    Returns a list of directories to check for community plugins in order of priority:
    1. User directory (~/.mmrelay/plugins/community)
    2. Local directory (plugins/community) for backward compatibility
    """
    dirs = []

    # Check user directory first (preferred location)
    user_dir = os.path.join(get_base_dir(), "plugins", "community")
    os.makedirs(user_dir, exist_ok=True)
    dirs.append(user_dir)

    # Check local directory (backward compatibility)
    local_dir = os.path.join(get_app_path(), "plugins", "community")
    dirs.append(local_dir)

    return dirs


def clone_or_update_repo(repo_url, tag, plugins_dir):
    # Extract the repository name from the URL
    repo_name = os.path.splitext(os.path.basename(repo_url.rstrip("/")))[0]
    repo_path = os.path.join(plugins_dir, repo_name)
    if os.path.isdir(repo_path):
        try:
            subprocess.check_call(["git", "-C", repo_path, "fetch"])
            subprocess.check_call(["git", "-C", repo_path, "checkout", tag])
            subprocess.check_call(["git", "-C", repo_path, "pull", "origin", tag])
            logger.info(f"Updated repository {repo_name} to {tag}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error updating repository {repo_name}: {e}")
            logger.error(
                f"Please manually git clone the repository {repo_url} into {repo_path}"
            )
            sys.exit(1)
    else:
        try:
            os.makedirs(plugins_dir, exist_ok=True)
            subprocess.check_call(
                ["git", "clone", "--branch", tag, repo_url], cwd=plugins_dir
            )
            logger.info(f"Cloned repository {repo_name} from {repo_url} at {tag}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error cloning repository {repo_name}: {e}")
            logger.error(
                f"Please manually git clone the repository {repo_url} into {repo_path}"
            )
            sys.exit(1)
    # Install requirements if requirements.txt exists
    requirements_path = os.path.join(repo_path, "requirements.txt")
    if os.path.isfile(requirements_path):
        try:
            # Use pip to install the requirements.txt
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", requirements_path]
            )
            logger.info(f"Installed requirements for plugin {repo_name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error installing requirements for plugin {repo_name}: {e}")
            logger.error(
                f"Please manually install the requirements from {requirements_path}"
            )
            sys.exit(1)


def load_plugins_from_directory(directory, recursive=False):
    plugins = []
    if os.path.isdir(directory):
        for root, _dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(".py"):
                    plugin_path = os.path.join(root, filename)
                    module_name = (
                        "plugin_"
                        + hashlib.sha256(plugin_path.encode("utf-8")).hexdigest()
                    )
                    spec = importlib.util.spec_from_file_location(
                        module_name, plugin_path
                    )
                    plugin_module = importlib.util.module_from_spec(spec)
                    try:
                        spec.loader.exec_module(plugin_module)
                        if hasattr(plugin_module, "Plugin"):
                            plugins.append(plugin_module.Plugin())
                        else:
                            logger.warning(
                                f"{plugin_path} does not define a Plugin class."
                            )
                    except Exception as e:
                        logger.error(f"Error loading plugin {plugin_path}: {e}")
            if not recursive:
                break
    else:
        if not plugins_loaded:  # Only log the missing directory once
            logger.debug(f"Directory {directory} does not exist.")
    return plugins


def load_plugins(passed_config=None):
    global sorted_active_plugins
    global plugins_loaded
    global config

    if plugins_loaded:
        return sorted_active_plugins

    logger.info("Checking plugin config...")

    # Update the global config if a config is passed
    if passed_config is not None:
        config = passed_config

    # Check if config is available
    if config is None:
        logger.error("No configuration available. Cannot load plugins.")
        return []

    # Import core plugins
    from mmrelay.plugins.debug_plugin import Plugin as DebugPlugin
    from mmrelay.plugins.drop_plugin import Plugin as DropPlugin
    from mmrelay.plugins.health_plugin import Plugin as HealthPlugin
    from mmrelay.plugins.help_plugin import Plugin as HelpPlugin
    from mmrelay.plugins.map_plugin import Plugin as MapPlugin
    from mmrelay.plugins.mesh_relay_plugin import Plugin as MeshRelayPlugin
    from mmrelay.plugins.nodes_plugin import Plugin as NodesPlugin
    from mmrelay.plugins.ping_plugin import Plugin as PingPlugin
    from mmrelay.plugins.telemetry_plugin import Plugin as TelemetryPlugin
    from mmrelay.plugins.weather_plugin import Plugin as WeatherPlugin

    # Initial list of core plugins
    core_plugins = [
        HealthPlugin(),
        MapPlugin(),
        MeshRelayPlugin(),
        PingPlugin(),
        TelemetryPlugin(),
        WeatherPlugin(),
        HelpPlugin(),
        NodesPlugin(),
        DropPlugin(),
        DebugPlugin(),
    ]

    plugins = core_plugins.copy()

    # Process and load custom plugins
    custom_plugins_config = config.get("custom-plugins", {})
    custom_plugin_dirs = get_custom_plugin_dirs()

    active_custom_plugins = [
        plugin_name
        for plugin_name, plugin_info in custom_plugins_config.items()
        if plugin_info.get("active", False)
    ]

    if active_custom_plugins:
        logger.debug(
            f"Loading active custom plugins: {', '.join(active_custom_plugins)}"
        )

    # Only load custom plugins that are explicitly enabled
    for plugin_name in active_custom_plugins:
        plugin_found = False

        # Try each directory in order
        for custom_dir in custom_plugin_dirs:
            plugin_path = os.path.join(custom_dir, plugin_name)
            if os.path.exists(plugin_path):
                logger.debug(f"Loading custom plugin from: {plugin_path}")
                plugins.extend(
                    load_plugins_from_directory(plugin_path, recursive=False)
                )
                plugin_found = True
                break

        if not plugin_found:
            logger.warning(
                f"Custom plugin '{plugin_name}' not found in any of the plugin directories"
            )

    # Process and download community plugins
    community_plugins_config = config.get("community-plugins", {})
    community_plugin_dirs = get_community_plugin_dirs()

    # Get the first directory for cloning (prefer user directory)
    community_plugins_dir = community_plugin_dirs[
        -1
    ]  # Use the user directory for new clones

    # Create community plugins directory if needed
    active_community_plugins = [
        plugin_name
        for plugin_name, plugin_info in community_plugins_config.items()
        if plugin_info.get("active", False)
    ]

    if active_community_plugins:
        # Ensure all community plugin directories exist
        for dir_path in community_plugin_dirs:
            os.makedirs(dir_path, exist_ok=True)

        logger.debug(
            f"Loading active community plugins: {', '.join(active_community_plugins)}"
        )

    # Only process community plugins if config section exists and is a dictionary
    if isinstance(community_plugins_config, dict):
        for plugin_name, plugin_info in community_plugins_config.items():
            if not plugin_info.get("active", False):
                logger.debug(
                    f"Skipping community plugin {plugin_name} - not active in config"
                )
                continue

            repo_url = plugin_info.get("repository")
            tag = plugin_info.get("tag", "master")
            if repo_url:
                # Clone to the user directory by default
                clone_or_update_repo(repo_url, tag, community_plugins_dir)
            else:
                logger.error("Repository URL not specified for a community plugin")
                logger.error("Please specify the repository URL in config.yaml")
                sys.exit(1)

    # Only load community plugins that are explicitly enabled
    for plugin_name in active_community_plugins:
        plugin_info = community_plugins_config[plugin_name]
        repo_url = plugin_info.get("repository")
        if repo_url:
            # Extract repository name from URL
            repo_name = os.path.splitext(os.path.basename(repo_url.rstrip("/")))[0]

            # Try each directory in order
            plugin_found = False
            for dir_path in community_plugin_dirs:
                plugin_path = os.path.join(dir_path, repo_name)
                if os.path.exists(plugin_path):
                    logger.debug(f"Loading community plugin from: {plugin_path}")
                    plugins.extend(
                        load_plugins_from_directory(plugin_path, recursive=True)
                    )
                    plugin_found = True
                    break

            if not plugin_found:
                logger.warning(
                    f"Community plugin '{repo_name}' not found in any of the plugin directories"
                )
        else:
            logger.error(
                f"Repository URL not specified for community plugin: {plugin_name}"
            )

    # Filter and sort active plugins by priority
    active_plugins = []
    for plugin in plugins:
        plugin_name = getattr(plugin, "plugin_name", plugin.__class__.__name__)

        # Determine if the plugin is active based on the configuration
        if plugin in core_plugins:
            # Core plugins: default to inactive unless specified otherwise
            plugin_config = config.get("plugins", {}).get(plugin_name, {})
            is_active = plugin_config.get("active", False)
        else:
            # Custom and community plugins: default to inactive unless specified
            if plugin_name in config.get("custom-plugins", {}):
                plugin_config = config.get("custom-plugins", {}).get(plugin_name, {})
            elif plugin_name in community_plugins_config:
                plugin_config = community_plugins_config.get(plugin_name, {})
            else:
                plugin_config = {}

            is_active = plugin_config.get("active", False)

        if is_active:
            plugin.priority = plugin_config.get(
                "priority", getattr(plugin, "priority", 100)
            )
            active_plugins.append(plugin)
            try:
                plugin.start()
            except Exception as e:
                logger.error(f"Error starting plugin {plugin_name}: {e}")

    sorted_active_plugins = sorted(active_plugins, key=lambda plugin: plugin.priority)

    # Log all loaded plugins
    if sorted_active_plugins:
        plugin_names = [
            getattr(plugin, "plugin_name", plugin.__class__.__name__)
            for plugin in sorted_active_plugins
        ]
        logger.info(f"Plugins loaded: {', '.join(plugin_names)}")
    else:
        logger.info("Plugins loaded: none")

    plugins_loaded = True  # Set the flag to indicate that plugins have been load
