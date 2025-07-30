#!/usr/bin/env python3
"""
Test suite for plugin loading system in MMRelay.

Tests the plugin discovery, loading, and management functionality including:
- Plugin directory discovery and prioritization
- Core plugin loading and initialization
- Custom plugin loading from filesystem
- Community plugin repository handling
- Plugin configuration and activation
- Plugin priority sorting and startup
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugin_loader import (
    get_community_plugin_dirs,
    get_custom_plugin_dirs,
    load_plugins,
    load_plugins_from_directory,
)


class MockPlugin:
    """Mock plugin class for testing."""
    
    def __init__(self, name="test_plugin", priority=10):
        self.plugin_name = name
        self.priority = priority
        self.started = False
        
    def start(self):
        """Mock start method."""
        self.started = True


class TestPluginLoader(unittest.TestCase):
    """Test cases for plugin loading functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for testing
        self.test_dir = tempfile.mkdtemp()
        self.custom_dir = os.path.join(self.test_dir, "plugins", "custom")
        self.community_dir = os.path.join(self.test_dir, "plugins", "community")
        
        os.makedirs(self.custom_dir, exist_ok=True)
        os.makedirs(self.community_dir, exist_ok=True)
        
        # Reset plugin loader state
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.plugins_loaded = False
        mmrelay.plugin_loader.sorted_active_plugins = []

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temporary directories
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('mmrelay.plugin_loader.get_base_dir')
    @patch('mmrelay.plugin_loader.get_app_path')
    @patch('os.makedirs')
    def test_get_custom_plugin_dirs(self, mock_makedirs, mock_get_app_path, mock_get_base_dir):
        """Test custom plugin directory discovery."""
        mock_get_base_dir.return_value = self.test_dir
        mock_get_app_path.return_value = "/app"

        dirs = get_custom_plugin_dirs()

        expected_dirs = [
            os.path.join(self.test_dir, "plugins", "custom"),
            "/app/plugins/custom"
        ]
        self.assertEqual(dirs, expected_dirs)
        mock_makedirs.assert_called_once()

    @patch('mmrelay.plugin_loader.get_base_dir')
    @patch('mmrelay.plugin_loader.get_app_path')
    @patch('os.makedirs')
    def test_get_community_plugin_dirs(self, mock_makedirs, mock_get_app_path, mock_get_base_dir):
        """Test community plugin directory discovery."""
        mock_get_base_dir.return_value = self.test_dir
        mock_get_app_path.return_value = "/app"

        dirs = get_community_plugin_dirs()

        expected_dirs = [
            os.path.join(self.test_dir, "plugins", "community"),
            "/app/plugins/community"
        ]
        self.assertEqual(dirs, expected_dirs)
        mock_makedirs.assert_called_once()

    def test_load_plugins_from_directory_empty(self):
        """Test loading plugins from empty directory."""
        plugins = load_plugins_from_directory(self.custom_dir)
        self.assertEqual(plugins, [])

    def test_load_plugins_from_directory_nonexistent(self):
        """Test loading plugins from non-existent directory."""
        nonexistent_dir = os.path.join(self.test_dir, "nonexistent")
        plugins = load_plugins_from_directory(nonexistent_dir)
        self.assertEqual(plugins, [])

    def test_load_plugins_from_directory_with_plugin(self):
        """Test loading a valid plugin from directory."""
        # Create a test plugin file
        plugin_content = '''
class Plugin:
    def __init__(self):
        self.plugin_name = "test_plugin"
        self.priority = 10
        
    def start(self):
        pass
'''
        plugin_file = os.path.join(self.custom_dir, "test_plugin.py")
        with open(plugin_file, 'w') as f:
            f.write(plugin_content)
        
        plugins = load_plugins_from_directory(self.custom_dir)
        
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].plugin_name, "test_plugin")
        self.assertEqual(plugins[0].priority, 10)

    def test_load_plugins_from_directory_no_plugin_class(self):
        """Test loading from directory with Python file but no Plugin class."""
        # Create a Python file without Plugin class
        plugin_content = '''
def some_function():
    pass
'''
        plugin_file = os.path.join(self.custom_dir, "not_a_plugin.py")
        with open(plugin_file, 'w') as f:
            f.write(plugin_content)
        
        plugins = load_plugins_from_directory(self.custom_dir)
        self.assertEqual(plugins, [])

    def test_load_plugins_from_directory_syntax_error(self):
        """Test loading from directory with Python file containing syntax error."""
        # Create a Python file with syntax error
        plugin_content = '''
class Plugin:
    def __init__(self):
        self.plugin_name = "broken_plugin"
        # Syntax error below
        if True
            pass
'''
        plugin_file = os.path.join(self.custom_dir, "broken_plugin.py")
        with open(plugin_file, 'w') as f:
            f.write(plugin_content)
        
        plugins = load_plugins_from_directory(self.custom_dir)
        self.assertEqual(plugins, [])

    @patch('mmrelay.plugins.health_plugin.Plugin')
    @patch('mmrelay.plugins.map_plugin.Plugin')
    @patch('mmrelay.plugins.help_plugin.Plugin')
    @patch('mmrelay.plugins.nodes_plugin.Plugin')
    @patch('mmrelay.plugins.drop_plugin.Plugin')
    @patch('mmrelay.plugins.debug_plugin.Plugin')
    @patch('mmrelay.plugins.weather_plugin.Plugin')
    def test_load_plugins_core_only(self, *mock_plugins):
        """Test loading core plugins only."""
        # Mock all core plugins
        for i, mock_plugin_class in enumerate(mock_plugins):
            mock_plugin = MockPlugin(f"core_plugin_{i}", priority=i)
            mock_plugin_class.return_value = mock_plugin
        
        # Set up minimal config with no custom plugins
        config = {
            "plugins": {
                f"core_plugin_{i}": {"active": True}
                for i in range(len(mock_plugins))
            }
        }
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        plugins = load_plugins(config)
        
        # Should have loaded all core plugins
        self.assertEqual(len(plugins), len(mock_plugins))
        
        # Verify plugins are sorted by priority
        for i in range(len(plugins) - 1):
            self.assertLessEqual(plugins[i].priority, plugins[i + 1].priority)
        
        # Verify all plugins were started
        for plugin in plugins:
            self.assertTrue(plugin.started)

    @patch('mmrelay.plugins.health_plugin.Plugin')
    @patch('mmrelay.plugins.map_plugin.Plugin')
    @patch('mmrelay.plugins.help_plugin.Plugin')
    @patch('mmrelay.plugins.nodes_plugin.Plugin')
    @patch('mmrelay.plugins.drop_plugin.Plugin')
    @patch('mmrelay.plugins.debug_plugin.Plugin')
    @patch('mmrelay.plugins.weather_plugin.Plugin')
    def test_load_plugins_inactive_plugins(self, *mock_plugins):
        """Test that inactive plugins are not loaded."""
        # Mock core plugins
        for i, mock_plugin_class in enumerate(mock_plugins):
            mock_plugin = MockPlugin(f"core_plugin_{i}", priority=i)
            mock_plugin_class.return_value = mock_plugin
        
        # Set up config with some plugins inactive
        config = {
            "plugins": {
                "core_plugin_0": {"active": True},
                "core_plugin_1": {"active": False},  # Inactive
                "core_plugin_2": {"active": True},
            }
        }
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        plugins = load_plugins(config)
        
        # Should only load active plugins
        active_plugin_names = [p.plugin_name for p in plugins]
        self.assertIn("core_plugin_0", active_plugin_names)
        self.assertNotIn("core_plugin_1", active_plugin_names)
        self.assertIn("core_plugin_2", active_plugin_names)

    @patch('mmrelay.plugin_loader.get_custom_plugin_dirs')
    @patch('mmrelay.plugins.health_plugin.Plugin')
    @patch('mmrelay.plugins.map_plugin.Plugin')
    @patch('mmrelay.plugins.help_plugin.Plugin')
    @patch('mmrelay.plugins.nodes_plugin.Plugin')
    @patch('mmrelay.plugins.drop_plugin.Plugin')
    @patch('mmrelay.plugins.debug_plugin.Plugin')
    @patch('mmrelay.plugins.weather_plugin.Plugin')
    def test_load_plugins_with_custom(self, *args):
        """Test loading plugins with custom plugins."""
        mock_get_custom_plugin_dirs = args[0]
        mock_plugins = args[1:]
        
        # Mock core plugins
        for i, mock_plugin_class in enumerate(mock_plugins):
            mock_plugin = MockPlugin(f"core_plugin_{i}", priority=i)
            mock_plugin_class.return_value = mock_plugin
        
        # Set up custom plugin directory
        mock_get_custom_plugin_dirs.return_value = [self.custom_dir]
        
        # Create a custom plugin
        custom_plugin_dir = os.path.join(self.custom_dir, "my_custom_plugin")
        os.makedirs(custom_plugin_dir, exist_ok=True)
        
        plugin_content = '''
class Plugin:
    def __init__(self):
        self.plugin_name = "my_custom_plugin"
        self.priority = 5
        
    def start(self):
        pass
'''
        plugin_file = os.path.join(custom_plugin_dir, "plugin.py")
        with open(plugin_file, 'w') as f:
            f.write(plugin_content)
        
        # Set up config with custom plugin active
        config = {
            "plugins": {
                "core_plugin_0": {"active": True},
            },
            "custom-plugins": {
                "my_custom_plugin": {"active": True}
            }
        }
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        plugins = load_plugins(config)
        
        # Should have loaded both core and custom plugins
        plugin_names = [p.plugin_name for p in plugins]
        self.assertIn("core_plugin_0", plugin_names)
        self.assertIn("my_custom_plugin", plugin_names)

    def test_load_plugins_caching(self):
        """Test that plugins are cached after first load."""
        config = {"plugins": {}}
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        # First load
        plugins1 = load_plugins(config)
        
        # Second load should return cached result
        plugins2 = load_plugins(config)
        
        self.assertIs(plugins1, plugins2)

    @patch('mmrelay.plugins.health_plugin.Plugin')
    def test_load_plugins_start_error(self, mock_health_plugin):
        """Test handling of plugin start() method errors."""
        # Create a plugin that raises an error on start
        mock_plugin = MockPlugin("error_plugin")
        mock_plugin.start = MagicMock(side_effect=Exception("Start failed"))
        mock_health_plugin.return_value = mock_plugin
        
        config = {
            "plugins": {
                "error_plugin": {"active": True}
            }
        }
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        # Should not raise exception, just log error
        plugins = load_plugins(config)
        
        # Plugin should still be in the list even if start() failed
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].plugin_name, "error_plugin")


if __name__ == "__main__":
    unittest.main()
