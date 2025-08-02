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

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        """
        Handle an incoming Meshtastic message.

        Returns:
            bool: Always returns False, indicating the message was not handled.
        """
        return False

    async def handle_room_message(self, room, event, full_message):
        """
        Handle a Matrix room message event.

        Parameters:
            room: The Matrix room where the event occurred.
            event: The Matrix event object.
            full_message: The full message content.

        Returns:
            bool: Always returns False, indicating the message was not handled.
        """
        return False


class TestBasePlugin(unittest.TestCase):
    """Test cases for the BasePlugin class."""

    def setUp(self):
        """
        Prepare the test environment by mocking configuration and database functions for plugin tests.
        """
        # Mock the global config
        self.mock_config = {
            "plugins": {"test_plugin": {"active": True, "channels": [0, 1]}},
            "meshtastic": {"message_delay": 3.0},
            "matrix": {
                "rooms": [
                    {"id": "!room1:matrix.org", "meshtastic_channel": 0},
                    {"id": "!room2:matrix.org", "meshtastic_channel": 1},
                ]
            },
        }

        # Patch the global config
        patcher = patch("mmrelay.plugins.base_plugin.config", self.mock_config)
        patcher.start()
        self.addCleanup(patcher.stop)

        # Mock database functions
        self.mock_store_plugin_data = patch(
            "mmrelay.plugins.base_plugin.store_plugin_data"
        ).start()
        self.mock_get_plugin_data = patch(
            "mmrelay.plugins.base_plugin.get_plugin_data"
        ).start()
        self.mock_get_plugin_data_for_node = patch(
            "mmrelay.plugins.base_plugin.get_plugin_data_for_node"
        ).start()
        self.mock_delete_plugin_data = patch(
            "mmrelay.plugins.base_plugin.delete_plugin_data"
        ).start()

        self.addCleanup(patch.stopall)

    def test_plugin_initialization_with_class_name(self):
        """Test plugin initialization using class-level plugin_name."""
        plugin = MockPlugin()

        self.assertEqual(plugin.plugin_name, "test_plugin")
        self.assertEqual(plugin.max_data_rows_per_node, 100)
        self.assertEqual(plugin.priority, 10)
        self.assertTrue(plugin.config["active"])

    def test_plugin_initialization_with_parameter_name(self):
        """
        Test that a plugin can be initialized with a custom plugin_name parameter.

        Verifies that the plugin_name attribute is set to the provided value during initialization.
        """
        plugin = MockPlugin(plugin_name="custom_name")

        self.assertEqual(plugin.plugin_name, "custom_name")

    def test_plugin_initialization_no_name_raises_error(self):
        """
        Test that initializing a plugin without a plugin name raises a ValueError.

        Ensures that a subclass of BasePlugin without a defined plugin_name triggers a ValueError during instantiation.
        """

        class NoNamePlugin(BasePlugin):
            async def handle_meshtastic_message(
                self, packet, formatted_message, longname, meshnet_name
            ):
                """
                Handle an incoming Meshtastic message.

                Returns:
                    bool: Always returns False, indicating the message was not handled.
                """
                return False

            async def handle_room_message(self, room, event, full_message):
                """
                Handle a Matrix room message event.

                Parameters:
                        room: The Matrix room where the event occurred.
                        event: The Matrix event object.
                        full_message: The full message content.

                Returns:
                        bool: Always returns False, indicating the message was not handled.
                """
                return False

        with self.assertRaises(ValueError) as context:
            NoNamePlugin()

        self.assertIn("missing plugin_name definition", str(context.exception))

    def test_description_property_default(self):
        """Test that description property returns empty string by default."""
        plugin = MockPlugin()
        self.assertEqual(plugin.description, "")

    def test_config_loading_with_plugin_config(self):
        """
        Test that the plugin loads configuration values correctly when a plugin config is present.

        Verifies that the plugin is active, the response delay is set to 3.0 seconds, and the enabled channels are [0, 1] when these values are provided in the configuration.
        """
        plugin = MockPlugin()

        self.assertTrue(plugin.config["active"])
        self.assertEqual(plugin.response_delay, 3.0)
        self.assertEqual(plugin.channels, [0, 1])

    def test_config_loading_without_plugin_config(self):
        """
        Test that the plugin uses default settings when no plugin-specific configuration is provided.

        Verifies that the plugin is inactive, sets the response delay to 2.0 seconds, and has no enabled channels if its configuration is missing.
        """
        # Remove plugin config
        config_without_plugin = {"plugins": {}}

        with patch("mmrelay.plugins.base_plugin.config", config_without_plugin):
            plugin = MockPlugin()

            self.assertFalse(plugin.config["active"])
            self.assertEqual(plugin.response_delay, 2.0)  # DEFAULT_MESSAGE_DELAY
            self.assertEqual(plugin.channels, [])

    def test_response_delay_minimum_enforcement(self):
        """
        Test that the plugin enforces a minimum response delay of 2.0 seconds when configured with a lower value.
        """
        config_low_delay = {
            "plugins": {"test_plugin": {"active": True}},
            "meshtastic": {"message_delay": 0.5},  # Below minimum
        }

        with patch("mmrelay.plugins.base_plugin.config", config_low_delay):
            plugin = MockPlugin()
            self.assertEqual(
                plugin.response_delay, 2.0
            )  # Should be enforced to minimum

    def test_get_response_delay(self):
        """
        Test that the get_response_delay method returns the configured response delay value.
        """
        plugin = MockPlugin()
        self.assertEqual(plugin.get_response_delay(), 3.0)

    def test_store_node_data(self):
        """
        Tests that the store_node_data method appends new data to a node's existing plugin data by first retrieving current data.
        """
        plugin = MockPlugin()
        test_data = {"key": "value", "timestamp": 1234567890}

        plugin.store_node_data("!node123", test_data)

        # store_node_data appends to existing data, so it calls get first
        self.mock_get_plugin_data_for_node.assert_called_once_with(
            "test_plugin", "!node123"
        )

    def test_get_node_data(self):
        """
        Tests that the get_node_data method retrieves the correct data for a given node from the plugin database.
        """
        plugin = MockPlugin()
        expected_data = [{"key": "value"}]
        self.mock_get_plugin_data_for_node.return_value = expected_data

        result = plugin.get_node_data("!node123")

        self.assertEqual(result, expected_data)
        self.mock_get_plugin_data_for_node.assert_called_once_with(
            "test_plugin", "!node123"
        )

    def test_set_node_data(self):
        """
        Test that set_node_data correctly replaces the data for a specific node.

        Verifies that calling set_node_data stores the provided data for the given node, replacing any existing data.
        """
        plugin = MockPlugin()
        test_data = [{"key": "value"}]

        plugin.set_node_data("!node123", test_data)

        self.mock_store_plugin_data.assert_called_once_with(
            "test_plugin", "!node123", test_data
        )

    def test_get_data(self):
        """
        Tests that the get_data method retrieves all plugin data using the correct plugin name.
        """
        plugin = MockPlugin()
        expected_data = [{"node": "!node123", "data": {"key": "value"}}]
        self.mock_get_plugin_data.return_value = expected_data

        result = plugin.get_data()

        self.assertEqual(result, expected_data)
        self.mock_get_plugin_data.assert_called_once_with("test_plugin")

    def test_delete_node_data(self):
        """
        Tests that the delete_node_data method removes plugin data for a specific node by calling the appropriate database function.
        """
        plugin = MockPlugin()

        plugin.delete_node_data("!node123")

        self.mock_delete_plugin_data.assert_called_once_with("test_plugin", "!node123")

    def test_is_channel_enabled_with_enabled_channel(self):
        """
        Test that is_channel_enabled returns True for a channel that is enabled in the plugin configuration.
        """
        plugin = MockPlugin()

        result = plugin.is_channel_enabled(0)
        self.assertTrue(result)

    def test_is_channel_enabled_with_disabled_channel(self):
        """
        Test that is_channel_enabled returns False for a channel not listed as enabled in the plugin configuration.
        """
        plugin = MockPlugin()

        result = plugin.is_channel_enabled(2)  # Not in channels list
        self.assertFalse(result)

    def test_is_channel_enabled_with_direct_message(self):
        """
        Test that is_channel_enabled returns True for direct messages, regardless of channel configuration.
        """
        plugin = MockPlugin()

        # Even disabled channel should be enabled for direct messages
        result = plugin.is_channel_enabled(2, is_direct_message=True)
        self.assertTrue(result)

    def test_is_channel_enabled_no_channels_configured(self):
        """
        Verifies that is_channel_enabled returns False for all channels when no channels are configured, except for direct messages which remain enabled.
        """
        config_no_channels = {
            "plugins": {
                "test_plugin": {
                    "active": True
                    # No channels configured
                }
            }
        }

        with patch("mmrelay.plugins.base_plugin.config", config_no_channels):
            plugin = MockPlugin()

            # Should return False for any channel when none configured
            result = plugin.is_channel_enabled(0)
            self.assertFalse(result)

            # But should still allow direct messages
            result = plugin.is_channel_enabled(0, is_direct_message=True)
            self.assertTrue(result)

    @patch("mmrelay.matrix_utils.bot_command")
    def test_matches_method(self, mock_bot_command):
        """
        Test that the plugin's matches method correctly identifies Matrix events as matching or not based on the bot_command utility.

        Verifies that the matches method returns True when the event matches a command and False otherwise.
        """
        plugin = MockPlugin()
        event = MagicMock()

        mock_bot_command.return_value = True
        result = plugin.matches(event)
        self.assertTrue(result)

        mock_bot_command.return_value = False
        result = plugin.matches(event)
        self.assertFalse(result)

    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_send_matrix_message(self, mock_connect_matrix):
        """
        Test that the send_matrix_message method sends a message to the specified Matrix room using the Matrix client.

        Verifies that the Matrix client's room_send method is called with the correct room ID and message type.
        """
        plugin = MockPlugin()
        mock_matrix_client = AsyncMock()
        mock_connect_matrix.return_value = mock_matrix_client

        async def run_test():
            """
            Asynchronously tests that sending a Matrix message via the plugin calls the Matrix client's room_send method with the correct parameters.
            """
            await plugin.send_matrix_message(
                "!room:matrix.org", "Test message", formatted=True
            )

            # Should call room_send on the matrix client
            mock_matrix_client.room_send.assert_called_once()
            call_args = mock_matrix_client.room_send.call_args
            self.assertEqual(call_args.kwargs["room_id"], "!room:matrix.org")
            self.assertEqual(call_args.kwargs["message_type"], "m.room.message")

        import asyncio

        asyncio.run(run_test())

    def test_strip_raw_method(self):
        """
        Test that the strip_raw method removes the 'raw' field from a packet dictionary if present.
        """
        plugin = MockPlugin()

        # Test with packet containing raw data
        packet_with_raw = {"decoded": {"text": "hello"}, "raw": "binary_data_here"}

        result = plugin.strip_raw(packet_with_raw)

        expected = {"decoded": {"text": "hello"}}
        self.assertEqual(result, expected)

    def test_strip_raw_method_no_raw_data(self):
        """
        Test that the strip_raw method returns the packet unchanged when no raw data is present.
        """
        plugin = MockPlugin()

        packet_without_raw = {"decoded": {"text": "hello"}}
        result = plugin.strip_raw(packet_without_raw)

        # Should return unchanged
        self.assertEqual(result, packet_without_raw)

    @patch("mmrelay.plugins.base_plugin.queue_message")
    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_send_message(self, mock_connect_meshtastic, mock_queue_message):
        """
        Test that the plugin's send_message method queues a Meshtastic message with the correct parameters.

        Verifies that the message is sent using the mocked Meshtastic client and that the queue_message function is called with the expected arguments.
        """
        plugin = MockPlugin()

        # Mock meshtastic client
        mock_client = MagicMock()
        mock_connect_meshtastic.return_value = mock_client
        mock_queue_message.return_value = True

        plugin.send_message("Test message", channel=1, destination_id="!node123")

        # Should queue the message (result depends on queue state, but call should happen)
        mock_queue_message.assert_called_once()
        call_args = mock_queue_message.call_args
        self.assertEqual(
            call_args[0][0], mock_client.sendText
        )  # First arg is the function
        self.assertIn("text", call_args[1])  # kwargs should contain text
        self.assertEqual(call_args[1]["text"], "Test message")

    def test_get_matrix_commands_default(self):
        """
        Test that get_matrix_commands returns a list containing the plugin name by default.
        """
        plugin = MockPlugin()
        self.assertEqual(plugin.get_matrix_commands(), ["test_plugin"])

    def test_get_mesh_commands_default(self):
        """
        Test that the default get_mesh_commands method returns an empty list.
        """
        plugin = MockPlugin()
        self.assertEqual(plugin.get_mesh_commands(), [])

    def test_get_plugin_data_dir(self):
        """
        Tests that the get_plugin_data_dir method returns the correct plugin data directory path using the patched utility function.
        """
        plugin = MockPlugin()

        with patch("mmrelay.plugins.base_plugin.get_plugin_data_dir") as mock_get_dir:
            mock_get_dir.return_value = "/path/to/plugin/data"

            result = plugin.get_plugin_data_dir()

            self.assertEqual(result, "/path/to/plugin/data")
            mock_get_dir.assert_called_once_with("test_plugin")

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_get_my_node_id_success(self, mock_connect_meshtastic):
        """Test that get_my_node_id returns the correct node ID when available."""
        plugin = MockPlugin()

        # Mock meshtastic client with node info
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect_meshtastic.return_value = mock_client

        result = plugin.get_my_node_id()

        self.assertEqual(result, 123456789)
        mock_connect_meshtastic.assert_called_once()

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_get_my_node_id_caches_on_success(self, mock_connect_meshtastic):
        """Test that get_my_node_id caches the node ID on a successful call."""
        plugin = MockPlugin()
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect_meshtastic.return_value = mock_client

        # First call should connect and cache
        self.assertEqual(plugin.get_my_node_id(), 123456789)
        mock_connect_meshtastic.assert_called_once()

        # Second call should use the cache
        self.assertEqual(plugin.get_my_node_id(), 123456789)
        mock_connect_meshtastic.assert_called_once()  # Still called only once

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_get_my_node_id_no_client(self, mock_connect_meshtastic):
        """Test that get_my_node_id returns None when no client is available."""
        plugin = MockPlugin()

        mock_connect_meshtastic.return_value = None

        result = plugin.get_my_node_id()

        self.assertIsNone(result)

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_get_my_node_id_no_myinfo(self, mock_connect_meshtastic):
        """Test that get_my_node_id returns None when client has no myInfo."""
        plugin = MockPlugin()

        # Mock client without myInfo
        mock_client = MagicMock()
        mock_client.myInfo = None
        mock_connect_meshtastic.return_value = mock_client

        result = plugin.get_my_node_id()

        self.assertIsNone(result)

    @patch.object(MockPlugin, "get_my_node_id")
    def test_is_direct_message_true(self, mock_get_my_node_id):
        """Test that is_direct_message returns True for direct messages."""
        plugin = MockPlugin()
        mock_get_my_node_id.return_value = 123456789

        packet = {"to": 123456789}

        result = plugin.is_direct_message(packet)

        self.assertTrue(result)

    @patch.object(MockPlugin, "get_my_node_id")
    def test_is_direct_message_false(self, mock_get_my_node_id):
        """Test that is_direct_message returns False for broadcast messages."""
        plugin = MockPlugin()
        mock_get_my_node_id.return_value = 123456789

        packet = {"to": 987654321}  # Different node ID

        result = plugin.is_direct_message(packet)

        self.assertFalse(result)

    @patch.object(MockPlugin, "get_my_node_id")
    def test_is_direct_message_no_to_field(self, mock_get_my_node_id):
        """Test that is_direct_message returns False when packet has no 'to' field."""
        plugin = MockPlugin()
        mock_get_my_node_id.return_value = 123456789

        packet = {}  # No 'to' field

        result = plugin.is_direct_message(packet)

        self.assertFalse(result)

    @patch.object(MockPlugin, "get_my_node_id")
    def test_is_direct_message_no_node_id(self, mock_get_my_node_id):
        """Test that is_direct_message returns False when node ID is unavailable."""
        plugin = MockPlugin()
        mock_get_my_node_id.return_value = None

        packet = {"to": 123456789}

        result = plugin.is_direct_message(packet)

        self.assertFalse(result)

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_get_my_node_id_no_cache_no_client(self, mock_connect_meshtastic):
        """Test that get_my_node_id returns None when no client and no cache."""
        plugin = MockPlugin()

        # Ensure no cache exists
        if hasattr(plugin, "_my_node_id"):
            delattr(plugin, "_my_node_id")

        mock_connect_meshtastic.return_value = None

        result = plugin.get_my_node_id()

        self.assertIsNone(result)
        mock_connect_meshtastic.assert_called_once()

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_is_direct_message_with_none_node_id(self, mock_connect_meshtastic):
        """Test is_direct_message when get_my_node_id returns None."""
        plugin = MockPlugin()

        # Ensure no cache exists
        if hasattr(plugin, "_my_node_id"):
            delattr(plugin, "_my_node_id")

        # Mock connect_meshtastic to return None (no client)
        mock_connect_meshtastic.return_value = None

        packet = {"to": 123456789}

        result = plugin.is_direct_message(packet)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
