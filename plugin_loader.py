from plugins.health_plugin import Plugin as HealthPlugin
from plugins.map_plugin import Plugin as MapPlugin
from plugins.mesh_relay_plugin import Plugin as MeshRelayPlugin
from plugins.ping_plugin import Plugin as PingPlugin
from plugins.telemetry_plugin import Plugin as TelemetryPlugin
from plugins.weather_plugin import Plugin as WeatherPlugin

from log_utils import get_logger

logger = get_logger(name="Plugins")

active_plugins = []


def load_plugins():
    global plugins
    if active_plugins:
        return active_plugins

    plugins = [
        HealthPlugin(),
        MapPlugin(),
        MeshRelayPlugin(),
        PingPlugin(),
        TelemetryPlugin(),
        WeatherPlugin(),
    ]

    for plugin in plugins:
        if plugin.config["active"]:
            logger.info(f"Loaded {plugin.plugin_name}")
            active_plugins.append(plugin)

    return active_plugins
