import os
import importlib.util
import hashlib
from log_utils import get_logger

logger = get_logger(name="Plugins")
sorted_active_plugins = []

def load_plugins_from_directory(directory, recursive=False):
    plugins = []
    if os.path.isdir(directory):
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith('.py'):
                    plugin_path = os.path.join(root, filename)
                    module_name = "plugin_" + hashlib.md5(plugin_path.encode('utf-8')).hexdigest()
                    spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                    plugin_module = importlib.util.module_from_spec(spec)
                    try:
                        spec.loader.exec_module(plugin_module)
                        if hasattr(plugin_module, 'Plugin'):
                            plugins.append(plugin_module.Plugin())
                        else:
                            logger.warning(f"{plugin_path} does not define a Plugin class.")
                    except Exception as e:
                        logger.error(f"Error loading plugin {plugin_path}: {e}")
            if not recursive:
                break
    else:
        logger.warning(f"Directory {directory} does not exist.")
    return plugins

def load_plugins():
    global sorted_active_plugins
    if sorted_active_plugins:
        return sorted_active_plugins

    # Import core plugins
    from plugins.health_plugin import Plugin as HealthPlugin
    from plugins.map_plugin import Plugin as MapPlugin
    from plugins.mesh_relay_plugin import Plugin as MeshRelayPlugin
    from plugins.ping_plugin import Plugin as PingPlugin
    from plugins.telemetry_plugin import Plugin as TelemetryPlugin
    from plugins.weather_plugin import Plugin as WeatherPlugin
    from plugins.help_plugin import Plugin as HelpPlugin
    from plugins.nodes_plugin import Plugin as NodesPlugin
    from plugins.drop_plugin import Plugin as DropPlugin
    from plugins.debug_plugin import Plugin as DebugPlugin

    # Initial list of core plugins
    plugins = [
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

    # Load custom plugins (non-recursive)
    custom_plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins', 'custom')
    plugins.extend(load_plugins_from_directory(custom_plugins_dir, recursive=False))

    # Load community plugins (recursive)
    community_plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins', 'community')
    plugins.extend(load_plugins_from_directory(community_plugins_dir, recursive=True))

    # Filter and sort active plugins by priority
    active_plugins = []
    for plugin in plugins:
        if plugin.config.get("active", False):
            plugin.priority = plugin.config.get("priority", plugin.priority)
            active_plugins.append(plugin)
            try:
                plugin.start()
            except Exception as e:
                logger.error(f"Error starting plugin {plugin}: {e}")

    sorted_active_plugins = sorted(active_plugins, key=lambda plugin: plugin.priority)
    return sorted_active_plugins
