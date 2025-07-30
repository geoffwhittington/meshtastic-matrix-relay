import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugin_loader import load_plugins


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
        # Reset plugin loader state
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.plugins_loaded = False
        mmrelay.plugin_loader.sorted_active_plugins = []

    def test_load_plugins_returns_sorted_active_plugins(self):
        """Test that load_plugins returns the sorted_active_plugins list."""
        # Mock core plugins
        mock_plugins = []
        for i in range(3):
            mock_plugin = MockPlugin(f"plugin_{i}", priority=i)
            mock_plugins.append(mock_plugin)
        
        config = {
            "plugins": {
                f"plugin_{i}": {"active": True}
                for i in range(3)
            }
        }
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        with patch('mmrelay.plugins.health_plugin.Plugin', return_value=mock_plugins[0]), \
             patch('mmrelay.plugins.map_plugin.Plugin', return_value=mock_plugins[1]), \
             patch('mmrelay.plugins.help_plugin.Plugin', return_value=mock_plugins[2]), \
             patch('mmrelay.plugins.nodes_plugin.Plugin', return_value=MockPlugin("nodes", 10)), \
             patch('mmrelay.plugins.drop_plugin.Plugin', return_value=MockPlugin("drop", 10)), \
             patch('mmrelay.plugins.debug_plugin.Plugin', return_value=MockPlugin("debug", 10)):

            # Call load_plugins and verify it returns the sorted list
            result = load_plugins(config)
            
            # Should return a list of loaded plugins
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            
            # Verify plugins are sorted by priority
            for i in range(len(result) - 1):
                self.assertLessEqual(result[i].priority, result[i + 1].priority)

    def test_load_plugins_returns_empty_list_when_no_plugins(self):
        """Test that load_plugins returns empty list when no plugins are active."""
        config = {
            "plugins": {}
        }
        
        import mmrelay.plugin_loader
        mmrelay.plugin_loader.config = config
        
        result = load_plugins(config)
        
        # Should return an empty list
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_load_plugins_sets_plugins_loaded_flag(self):
        """Test that load_plugins sets the plugins_loaded flag to True."""
        config = {"plugins": {}}
        
        result = load_plugins(config)
        
        import mmrelay.plugin_loader
        self.assertTrue(mmrelay.plugin_loader.plugins_loaded)


if __name__ == "__main__":
    unittest.main()