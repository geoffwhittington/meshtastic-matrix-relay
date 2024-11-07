import os
import importlib.util
from log_utils import get_logger

logger = get_logger(name="Plugins")

sorted_active_plugins = []

def load_plugins():
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

    global sorted_active_plugins
    if sorted_active_plugins:
        return sorted_active_plugins

    # List of core plugins
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

    # Load custom plugins from the 'custom_plugins' directory
    custom_plugins_dir = os.path.join(os.path.dirname(__file__), 'custom_plugins')
    if os.path.isdir(custom_plugins_dir):
        for filename in os.listdir(custom_plugins_dir):
            if filename.endswith('.py'):
                plugin_path = os.path.join(custom_plugins_dir, filename)
                spec = importlib.util.spec_from_file_location("custom_plugin", plugin_path)
                custom_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(custom_module)
                if hasattr(custom_module, 'Plugin'):
                    plugins.append(custom_module.Plugin())
                else:
                    logger.warning(f"{filename} does not define a Plugin class.")

    # Filter and sort active plugins by priority
    active_plugins = []
    for plugin in plugins:
        if plugin.config.get("active", False):
            plugin.priority = plugin.config.get("priority", plugin.priority)
            active_plugins.append(plugin)
            plugin.start()

    sorted_active_plugins = sorted(active_plugins, key=lambda plugin: plugin.priority)
    return sorted_active_plugins
