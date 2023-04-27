import sys
import importlib
from pathlib import Path

plugins = []


def load_plugins():
    global plugins
    if plugins:
        return plugins

    plugins = []
    plugin_folder = Path("plugins")
    sys.path.insert(0, str(plugin_folder.resolve()))

    for plugin_file in plugin_folder.glob("*.py"):
        plugin_name = plugin_file.stem
        if plugin_name == "__init__":
            continue
        plugin_module = importlib.import_module(plugin_name)
        if hasattr(plugin_module, "Plugin"):
            plugins.append(plugin_module.Plugin())

    return plugins
