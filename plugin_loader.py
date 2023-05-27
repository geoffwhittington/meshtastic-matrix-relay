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

    active_plugins = []
    for plugin in plugins:
        if plugin.config["active"]:
            plugin.priority = (
                plugin.config["priority"]
                if "priority" in plugin.config
                else plugin.priority
            )
            logger.info(f"Loaded {plugin.plugin_name} ({plugin.priority})")
            active_plugins.append(plugin)

    sorted_active_plugins = sorted(active_plugins, key=lambda plugin: plugin.priority)
    return sorted_active_plugins
