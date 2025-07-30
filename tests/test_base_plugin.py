#!/usr/bin/env python3
"""
Test suite for the MMRelay base plugin class.

Tests the core plugin functionality including:
- Plugin initialization and name validation
- Configuration management and validation
- Database operations (store, get, delete plugin data)
- Channel enablement checking
- Matrix message sending capabilities
- Response delay calculation
- Command matching and routing
- Scheduling support
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.base_plugin import BasePlugin


class MockPlugin(BasePlugin):
    """Mock plugin implementation for testing BasePlugin functionality."""
    plugin_name = "test_plugin"

    async def handle_meshtastic_message(self, packet, formatted_message, longname, meshnet_name):
        return False

    async def handle_room_message(self, room, event, full_message):
        return False


class TestBasePlugin(unittest.TestCase):
    """Test cases for the BasePlugin class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the global config
        self.mock_config = {
            "plugins": {
                "test_plugin": {
                    "active": True,
                    "channels": [0, 1]
                }
            },
            "meshtastic": {
                "message_delay": 3.0
            },
            "matrix": {
                "rooms": [
                    {"id": "!room1:matrix.org", "meshtastic_channel": 0},
                    {"id": "!room2:matrix.org", "meshtastic_channel": 1}
                ]
            }
        }
        
        # Patch the global config
        patcher = patch('mmrelay.plugins.base_plugin.config', self.mock_config)
        patcher.start()
        self.addCleanup(patcher.stop)
        
        # Mock database functions
        self.mock_store_plugin_data = patch('mmrelay.plugins.base_plugin.store_plugin_data').start()
        self.mock_get_plugin_data = patch('mmrelay.plugins.base_plugin.get_plugin_data').start()
        self.mock_get_plugin_data_for_node = patch('mmrelay.plugins.base_plugin.get_plugin_data_for_node').start()
        self.mock_delete_plugin_data = patch('mmrelay.plugins.base_plugin.delete_plugin_data').start()
        
        self.addCleanup(patch.stopall)

    def test_plugin_initialization_with_class_name(self):
        """Test plugin initialization using class-level plugin_name."""
        plugin = MockPlugin()

        self.assertEqual(plugin.plugin_name, "test_plugin")
        self.assertEqual(plugin.max_data_rows_per_node, 100)
        self.assertEqual(plugin.priority, 10)
        self.assertTrue(plugin.config["active"])

    def test_plugin_initialization_with_parameter_name(self):
        """Test plugin initialization with plugin_name parameter."""
        plugin = MockPlugin(plugin_name="custom_name")

        self.assertEqual(plugin.plugin_name, "custom_name")

    def test_plugin_initialization_no_name_raises_error(self):
        """Test that plugin initialization without name raises ValueError."""
        class NoNamePlugin(BasePlugin):
            async def handle_meshtastic_message(self, packet, formatted_message, longname, meshnet_name):
                return False
            async def handle_room_message(self, room, event, full_message):
                return False
        
        with self.assertRaises(ValueError) as context:
            NoNamePlugin()
        
        self.assertIn("missing plugin_name definition", str(context.exception))

    def test_description_property_default(self):
        """Test that description property returns empty string by default."""
        plugin = MockPlugin()
        self.assertEqual(plugin.description, "")

    def test_config_loading_with_plugin_config(self):
        """Test configuration loading when plugin config exists."""
        plugin = MockPlugin()

        self.assertTrue(plugin.config["active"])
        self.assertEqual(plugin.response_delay, 3.0)
        self.assertEqual(plugin.channels, [0, 1])

    def test_config_loading_without_plugin_config(self):
        """Test configuration loading when plugin config doesn't exist."""
        # Remove plugin config
        config_without_plugin = {"plugins": {}}

        with patch('mmrelay.plugins.base_plugin.config', config_without_plugin):
            plugin = MockPlugin()

            self.assertFalse(plugin.config["active"])
            self.assertEqual(plugin.response_delay, 2.2)  # DEFAULT_MESSAGE_DELAY
            self.assertEqual(plugin.channels, [])

    def test_response_delay_minimum_enforcement(self):
        """Test that response delay is enforced to minimum 2.0 seconds."""
        config_low_delay = {
            "plugins": {
                "test_plugin": {
                    "active": True
                }
            },
            "meshtastic": {
                "message_delay": 0.5  # Below minimum
            }
        }

        with patch('mmrelay.plugins.base_plugin.config', config_low_delay):
            plugin = MockPlugin()
            self.assertEqual(plugin.response_delay, 2.0)  # Should be enforced to minimum

    def test_get_response_delay(self):
        """Test get_response_delay method."""
        plugin = MockPlugin()
        self.assertEqual(plugin.get_response_delay(), 3.0)

    def test_store_node_data(self):
        """Test store_node_data method."""
        plugin = MockPlugin()
        test_data = {"key": "value", "timestamp": 1234567890}

        plugin.store_node_data("!node123", test_data)

        # store_node_data appends to existing data, so it calls get first
        self.mock_get_plugin_data_for_node.assert_called_once_with("test_plugin", "!node123")

    def test_get_node_data(self):
        """Test get_node_data method."""
        plugin = MockPlugin()
        expected_data = [{"key": "value"}]
        self.mock_get_plugin_data_for_node.return_value = expected_data

        result = plugin.get_node_data("!node123")

        self.assertEqual(result, expected_data)
        self.mock_get_plugin_data_for_node.assert_called_once_with("test_plugin", "!node123")

    def test_set_node_data(self):
        """Test set_node_data method (replaces existing data)."""
        plugin = MockPlugin()
        test_data = [{"key": "value"}]

        plugin.set_node_data("!node123", test_data)

        self.mock_store_plugin_data.assert_called_once_with(
            "test_plugin", "!node123", test_data
        )

    def test_get_data(self):
        """Test get_data method."""
        plugin = MockPlugin()
        expected_data = [{"node": "!node123", "data": {"key": "value"}}]
        self.mock_get_plugin_data.return_value = expected_data

        result = plugin.get_data()

        self.assertEqual(result, expected_data)
        self.mock_get_plugin_data.assert_called_once_with("test_plugin")

    def test_delete_node_data(self):
        """Test delete_node_data method."""
        plugin = MockPlugin()

        plugin.delete_node_data("!node123")

        self.mock_delete_plugin_data.assert_called_once_with("test_plugin", "!node123")

    def test_is_channel_enabled_with_enabled_channel(self):
        """Test is_channel_enabled with enabled channel."""
        plugin = MockPlugin()

        result = plugin.is_channel_enabled(0)
        self.assertTrue(result)

    def test_is_channel_enabled_with_disabled_channel(self):
        """Test is_channel_enabled with disabled channel."""
        plugin = MockPlugin()

        result = plugin.is_channel_enabled(2)  # Not in channels list
        self.assertFalse(result)

    def test_is_channel_enabled_with_direct_message(self):
        """Test is_channel_enabled with direct message override."""
        plugin = MockPlugin()

        # Even disabled channel should be enabled for direct messages
        result = plugin.is_channel_enabled(2, is_direct_message=True)
        self.assertTrue(result)

    def test_is_channel_enabled_no_channels_configured(self):
        """Test is_channel_enabled when no channels are configured."""
        config_no_channels = {
            "plugins": {
                "test_plugin": {
                    "active": True
                    # No channels configured
                }
            }
        }

        with patch('mmrelay.plugins.base_plugin.config', config_no_channels):
            plugin = MockPlugin()

            # Should return False for any channel when none configured
            result = plugin.is_channel_enabled(0)
            self.assertFalse(result)

            # But should still allow direct messages
            result = plugin.is_channel_enabled(0, is_direct_message=True)
            self.assertTrue(result)

    @patch('mmrelay.matrix_utils.bot_command')
    def test_matches_method(self, mock_bot_command):
        """Test matches method for Matrix event matching."""
        plugin = MockPlugin()
        event = MagicMock()

        mock_bot_command.return_value = True
        result = plugin.matches(event)
        self.assertTrue(result)

        mock_bot_command.return_value = False
        result = plugin.matches(event)
        self.assertFalse(result)

    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_send_matrix_message(self, mock_connect_matrix):
        """Test send_matrix_message method."""
        plugin = MockPlugin()
        mock_matrix_client = AsyncMock()
        mock_connect_matrix.return_value = mock_matrix_client

        async def run_test():
            await plugin.send_matrix_message(
                "!room:matrix.org",
                "Test message",
                formatted=True
            )

            # Should call room_send on the matrix client
            mock_matrix_client.room_send.assert_called_once()
            call_args = mock_matrix_client.room_send.call_args
            self.assertEqual(call_args.kwargs['room_id'], "!room:matrix.org")
            self.assertEqual(call_args.kwargs['message_type'], "m.room.message")

        import asyncio
        asyncio.run(run_test())

    def test_strip_raw_method(self):
        """Test strip_raw method for removing raw packet data."""
        plugin = MockPlugin()

        # Test with packet containing raw data
        packet_with_raw = {
            "decoded": {"text": "hello"},
            "raw": "binary_data_here"
        }

        result = plugin.strip_raw(packet_with_raw)

        expected = {"decoded": {"text": "hello"}}
        self.assertEqual(result, expected)

    def test_strip_raw_method_no_raw_data(self):
        """Test strip_raw method with packet without raw data."""
        plugin = MockPlugin()

        packet_without_raw = {"decoded": {"text": "hello"}}
        result = plugin.strip_raw(packet_without_raw)

        # Should return unchanged
        self.assertEqual(result, packet_without_raw)

    @patch('mmrelay.plugins.base_plugin.queue_message')
    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_send_message(self, mock_connect_meshtastic, mock_queue_message):
        """Test send_message method."""
        plugin = MockPlugin()

        # Mock meshtastic client
        mock_client = MagicMock()
        mock_connect_meshtastic.return_value = mock_client
        mock_queue_message.return_value = True

        result = plugin.send_message("Test message", channel=1, destination_id="!node123")

        # Should queue the message (result depends on queue state, but call should happen)
        mock_queue_message.assert_called_once()
        call_args = mock_queue_message.call_args
        self.assertEqual(call_args[0][0], mock_client.sendText)  # First arg is the function
        self.assertIn("text", call_args[1])  # kwargs should contain text
        self.assertEqual(call_args[1]["text"], "Test message")

    def test_get_matrix_commands_default(self):
        """Test get_matrix_commands returns plugin name by default."""
        plugin = MockPlugin()
        self.assertEqual(plugin.get_matrix_commands(), ["test_plugin"])

    def test_get_mesh_commands_default(self):
        """Test get_mesh_commands returns empty list by default."""
        plugin = MockPlugin()
        self.assertEqual(plugin.get_mesh_commands(), [])

    def test_get_plugin_data_dir(self):
        """Test get_plugin_data_dir method."""
        plugin = MockPlugin()

        with patch('mmrelay.plugins.base_plugin.get_plugin_data_dir') as mock_get_dir:
            mock_get_dir.return_value = "/path/to/plugin/data"

            result = plugin.get_plugin_data_dir()

            self.assertEqual(result, "/path/to/plugin/data")
            mock_get_dir.assert_called_once_with("test_plugin")


if __name__ == "__main__":
    unittest.main()
