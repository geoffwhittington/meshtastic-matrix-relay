#!/usr/bin/env python3
"""
Test suite for the MMRelay drop plugin.

Tests the message drop and pickup functionality including:
- Message dropping with location validation
- Message pickup based on proximity
- Location-based filtering
- Node data storage and retrieval
- Error handling for invalid positions
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.drop_plugin import Plugin


class TestDropPlugin(unittest.TestCase):
    """Test cases for the drop plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.config = {"radius_km": 5}
        self.plugin.logger = MagicMock()
        
        # Mock meshtastic client
        self.mock_meshtastic_client = MagicMock()
        self.mock_meshtastic_client.nodes = {
            "node1": {
                "user": {"id": "!12345678"},
                "position": {"latitude": 40.7128, "longitude": -74.0060}
            },
            "node2": {
                "user": {"id": "!87654321"},
                "position": {"latitude": 40.7589, "longitude": -73.9851}
            },
            "node3": {
                "user": {"id": "!11111111"}
                # No position data
            }
        }
        self.mock_meshtastic_client.getMyNodeInfo.return_value = {
            "user": {"id": "!relay123"}
        }

    def test_get_position_with_valid_node(self):
        """Test getting position for a node that exists with position data."""
        position = self.plugin.get_position(self.mock_meshtastic_client, "!12345678")
        
        self.assertIsNotNone(position)
        self.assertEqual(position["latitude"], 40.7128)
        self.assertEqual(position["longitude"], -74.0060)

    def test_get_position_with_node_no_position(self):
        """Test getting position for a node that exists but has no position data."""
        position = self.plugin.get_position(self.mock_meshtastic_client, "!11111111")
        
        self.assertIsNone(position)

    def test_get_position_with_nonexistent_node(self):
        """Test getting position for a node that doesn't exist."""
        position = self.plugin.get_position(self.mock_meshtastic_client, "!99999999")
        
        self.assertIsNone(position)

    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_drop_valid(self, mock_connect):
        """Test dropping a message with valid position data."""
        mock_connect.return_value = self.mock_meshtastic_client

        # Mock plugin methods
        self.plugin.store_node_data = MagicMock()

        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!drop This is a test message"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)
            self.plugin.store_node_data.assert_called_once()
            call_args = self.plugin.store_node_data.call_args
            self.assertEqual(call_args[0][0], "!NODE_MSGS!")
            stored_data = call_args[0][1]
            self.assertEqual(stored_data["text"], "This is a test message")
            self.assertEqual(stored_data["originator"], "!12345678")
            self.assertEqual(stored_data["location"], (40.7128, -74.0060))

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_drop_no_position(self, mock_connect):
        """Test dropping a message when node has no position data."""
        mock_connect.return_value = self.mock_meshtastic_client

        packet = {
            "fromId": "!11111111",  # Node without position
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!drop This should fail"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)  # Returns True but doesn't store
            self.plugin.logger.debug.assert_called_with(
                "Position of dropping node is not known. Skipping ..."
            )

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_not_drop_command(self, mock_connect):
        """Test handling a message that's not a drop command."""
        mock_connect.return_value = self.mock_meshtastic_client

        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Just a regular message"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_invalid_drop_format(self, mock_connect):
        """Test handling a drop command with invalid format."""
        mock_connect.return_value = self.mock_meshtastic_client

        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!drop"  # No message content
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.haversine')
    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_pickup_in_range(self, mock_connect, mock_haversine):
        """Test picking up messages when in range."""
        mock_connect.return_value = self.mock_meshtastic_client
        mock_haversine.return_value = 1.0  # 1km distance, within 5km radius

        # Mock stored messages
        stored_messages = [
            {
                "location": (40.7128, -74.0060),  # Same as node1 location
                "text": "Pickup this message",
                "originator": "!99999999"  # Different from packet sender
            }
        ]

        self.plugin.get_node_data = MagicMock(return_value=stored_messages)
        self.plugin.set_node_data = MagicMock()

        packet = {
            "fromId": "!12345678",  # Node1 with position
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Some message"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should send the message to the node
            self.mock_meshtastic_client.sendText.assert_called_once_with(
                text="Pickup this message", destinationId="!12345678"
            )

            # Should clear the messages (empty list)
            self.plugin.set_node_data.assert_called_once_with("!NODE_MSGS!", [])

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.haversine')
    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_pickup_out_of_range(self, mock_connect, mock_haversine):
        """Test that messages out of range are not picked up."""
        mock_connect.return_value = self.mock_meshtastic_client
        mock_haversine.return_value = 10.0  # 10km distance, outside 5km radius

        # Mock stored messages at a distant location
        stored_messages = [
            {
                "location": (41.0000, -75.0000),  # Far from node1 location
                "text": "Distant message",
                "originator": "!99999999"
            }
        ]

        self.plugin.get_node_data = MagicMock(return_value=stored_messages)
        self.plugin.set_node_data = MagicMock()

        packet = {
            "fromId": "!12345678",  # Node1 with position
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Some message"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should not send the message
            self.mock_meshtastic_client.sendText.assert_not_called()

            # Should keep the message in storage
            self.plugin.set_node_data.assert_called_once_with("!NODE_MSGS!", stored_messages)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.haversine')
    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_skip_own_messages(self, mock_connect, mock_haversine):
        """Test that nodes cannot pickup their own dropped messages."""
        mock_connect.return_value = self.mock_meshtastic_client
        mock_haversine.return_value = 1.0  # 1km distance, within range

        # Mock stored messages from the same originator
        stored_messages = [
            {
                "location": (40.7128, -74.0060),
                "text": "Own message",
                "originator": "!12345678"  # Same as packet sender
            }
        ]

        self.plugin.get_node_data = MagicMock(return_value=stored_messages)
        self.plugin.set_node_data = MagicMock()

        packet = {
            "fromId": "!12345678",  # Same as originator
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Some message"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should not send the message
            self.mock_meshtastic_client.sendText.assert_not_called()

            # Should keep the message in storage (can't pick up own messages)
            self.plugin.set_node_data.assert_called_once_with("!NODE_MSGS!", stored_messages)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.haversine')
    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_distance_calculation_error(self, mock_connect, mock_haversine):
        """Test handling of distance calculation errors."""
        mock_connect.return_value = self.mock_meshtastic_client
        mock_haversine.side_effect = ValueError("Invalid coordinates")  # Simulate error

        # Mock stored messages with invalid location data
        stored_messages = [
            {
                "location": "invalid_location",  # Invalid location format
                "text": "Message with bad location",
                "originator": "!99999999"
            }
        ]

        self.plugin.get_node_data = MagicMock(return_value=stored_messages)
        self.plugin.set_node_data = MagicMock()

        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Some message"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should not send the message (distance defaults to 1000km, out of range)
            self.mock_meshtastic_client.sendText.assert_not_called()

            # Should keep the message in storage
            self.plugin.set_node_data.assert_called_once_with("!NODE_MSGS!", stored_messages)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.drop_plugin.connect_meshtastic')
    def test_handle_meshtastic_message_from_relay_node(self, mock_connect):
        """Test that messages from the relay node itself are ignored for pickup."""
        mock_connect.return_value = self.mock_meshtastic_client

        packet = {
            "fromId": "!relay123",  # Same as relay node ID
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Message from relay"
            }
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return False for non-drop messages (not processed)
            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())

    def test_handle_room_message_with_matching_command(self):
        """Test handling Matrix room messages with matching commands."""
        # Mock the matches method to return True
        self.plugin.matches = MagicMock(return_value=True)

        room = MagicMock()
        event = MagicMock()

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")
            self.assertTrue(result)
            self.plugin.matches.assert_called_once_with(event)

        import asyncio
        asyncio.run(run_test())

    def test_handle_room_message_without_matching_command(self):
        """Test handling Matrix room messages without matching commands."""
        # Mock the matches method to return False
        self.plugin.matches = MagicMock(return_value=False)

        room = MagicMock()
        event = MagicMock()

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")
            self.assertIsNone(result)  # Returns None when no match
            self.plugin.matches.assert_called_once_with(event)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
