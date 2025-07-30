#!/usr/bin/env python3
"""
Test suite for the MMRelay mesh relay plugin.

Tests the core mesh-to-Matrix relay functionality including:
- Packet normalization and processing
- Bidirectional message relay
- Channel mapping and configuration
- Matrix event matching
- Meshtastic packet reconstruction
"""

import base64
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.mesh_relay_plugin import Plugin


class TestMeshRelayPlugin(unittest.TestCase):
    """Test cases for the mesh relay plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        
        # Mock the strip_raw method from base plugin
        self.plugin.strip_raw = MagicMock(side_effect=lambda x: x)

    def test_plugin_name(self):
        """Test that plugin name is correctly set."""
        self.assertEqual(self.plugin.plugin_name, "mesh_relay")

    def test_max_data_rows_per_node(self):
        """Test that max data rows per node is set correctly."""
        self.assertEqual(self.plugin.max_data_rows_per_node, 50)

    def test_get_matrix_commands(self):
        """Test that get_matrix_commands returns empty list."""
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, [])

    def test_get_mesh_commands(self):
        """Test that get_mesh_commands returns empty list."""
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, [])

    def test_normalize_dict_input(self):
        """Test normalize method with dictionary input."""
        input_dict = {"decoded": {"text": "test message"}}
        
        result = self.plugin.normalize(input_dict)
        
        # Should call strip_raw and return the result
        self.plugin.strip_raw.assert_called_once_with(input_dict)
        self.assertEqual(result, input_dict)

    def test_normalize_json_string_input(self):
        """Test normalize method with JSON string input."""
        input_json = '{"decoded": {"text": "test message"}}'
        expected_dict = {"decoded": {"text": "test message"}}
        
        result = self.plugin.normalize(input_json)
        
        # Should parse JSON and call strip_raw
        self.plugin.strip_raw.assert_called_once_with(expected_dict)
        self.assertEqual(result, expected_dict)

    def test_normalize_plain_string_input(self):
        """Test normalize method with plain string input."""
        input_string = "plain text message"
        expected_dict = {"decoded": {"text": "plain text message"}}
        
        result = self.plugin.normalize(input_string)
        
        # Should wrap in TEXT_MESSAGE_APP format
        self.plugin.strip_raw.assert_called_once_with(expected_dict)
        self.assertEqual(result, expected_dict)

    def test_normalize_invalid_json_input(self):
        """Test normalize method with invalid JSON string."""
        input_string = '{"invalid": json}'
        expected_dict = {"decoded": {"text": '{"invalid": json}'}}
        
        result = self.plugin.normalize(input_string)
        
        # Should treat as plain string when JSON parsing fails
        self.plugin.strip_raw.assert_called_once_with(expected_dict)
        self.assertEqual(result, expected_dict)

    def test_process_packet_without_payload(self):
        """Test process method with packet without binary payload."""
        packet = {"decoded": {"text": "test message"}}
        
        result = self.plugin.process(packet)
        
        # Should normalize but not modify payload
        self.assertEqual(result, packet)

    def test_process_packet_with_binary_payload(self):
        """Test process method with packet containing binary payload."""
        binary_data = b"binary payload data"
        packet = {"decoded": {"payload": binary_data}}
        
        result = self.plugin.process(packet)
        
        # Should encode binary payload as base64
        expected_payload = base64.b64encode(binary_data).decode("utf-8")
        self.assertEqual(result["decoded"]["payload"], expected_payload)

    def test_process_packet_with_string_payload(self):
        """Test process method with packet containing string payload."""
        packet = {"decoded": {"payload": "string payload"}}
        
        result = self.plugin.process(packet)
        
        # Should not modify string payload
        self.assertEqual(result["decoded"]["payload"], "string payload")

    def test_matches_valid_radio_packet_message(self):
        """Test matches method with valid radio packet message."""
        event = MagicMock()
        event.source = {
            "content": {
                "body": "Processed TEXT_MESSAGE_APP radio packet"
            }
        }
        
        result = self.plugin.matches(event)
        
        self.assertTrue(result)

    def test_matches_invalid_message_format(self):
        """Test matches method with invalid message format."""
        event = MagicMock()
        event.source = {
            "content": {
                "body": "This is not a radio packet message"
            }
        }
        
        result = self.plugin.matches(event)
        
        self.assertFalse(result)

    def test_matches_missing_content(self):
        """Test matches method with missing content."""
        event = MagicMock()
        event.source = {}
        
        result = self.plugin.matches(event)
        
        self.assertFalse(result)

    def test_matches_non_string_body(self):
        """Test matches method with non-string body."""
        event = MagicMock()
        event.source = {
            "content": {
                "body": 123  # Non-string body
            }
        }
        
        result = self.plugin.matches(event)
        
        self.assertFalse(result)

    @patch('mmrelay.plugins.mesh_relay_plugin.config', None)
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_meshtastic_message_no_config(self, mock_connect):
        """Test handle_meshtastic_message with no configuration."""
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"},
            "channel": 0
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return None when no config
            self.assertIsNone(result)

            # Should not send any Matrix messages
            mock_matrix_client.room_send.assert_not_called()

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_meshtastic_message_unmapped_channel(self, mock_connect, mock_config):
        """Test handle_meshtastic_message with unmapped channel."""
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        # Mock config with no matching channel
        mock_config.get.return_value = [
            {"meshtastic_channel": 1, "id": "!room1:matrix.org"}
        ]

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"},
            "channel": 0  # Channel 0 not mapped
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return None for unmapped channel
            self.assertIsNone(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with(
                "Skipping message from unmapped channel 0"
            )

            # Should not send any Matrix messages
            mock_matrix_client.room_send.assert_not_called()

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_meshtastic_message_mapped_channel(self, mock_connect, mock_config):
        """Test handle_meshtastic_message with mapped channel."""
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        # Mock config with matching channel
        mock_config.get.return_value = [
            {"meshtastic_channel": 0, "id": "!room1:matrix.org"}
        ]

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"},
            "channel": 0
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return False (allows other plugins to process)
            self.assertFalse(result)

            # Should send Matrix message
            mock_matrix_client.room_send.assert_called_once()
            call_args = mock_matrix_client.room_send.call_args

            self.assertEqual(call_args.kwargs['room_id'], "!room1:matrix.org")
            self.assertEqual(call_args.kwargs['message_type'], "m.room.message")

            content = call_args.kwargs['content']
            self.assertEqual(content['msgtype'], "m.text")
            self.assertTrue(content['mmrelay_suppress'])
            self.assertIn("meshtastic_packet", content)
            self.assertEqual(content['body'], "Processed TEXT_MESSAGE_APP radio packet")

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_meshtastic_message_no_channel_field(self, mock_connect, mock_config):
        """Test handle_meshtastic_message with packet missing channel field."""
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        # Mock config with channel 0 mapped (default channel)
        mock_config.get.return_value = [
            {"meshtastic_channel": 0, "id": "!room1:matrix.org"}
        ]

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"}
            # No channel field - should default to 0
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return False and send message (channel defaults to 0)
            self.assertFalse(result)
            mock_matrix_client.room_send.assert_called_once()

        import asyncio
        asyncio.run(run_test())

    def test_handle_room_message_no_match(self):
        """Test handle_room_message when event doesn't match."""
        self.plugin.matches = MagicMock(return_value=False)

        room = MagicMock()
        event = MagicMock()

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")
            self.assertFalse(result)
            self.plugin.matches.assert_called_once_with(event)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config', None)
    def test_handle_room_message_no_config(self):
        """Test handle_room_message with no configuration."""
        self.plugin.matches = MagicMock(return_value=True)

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return False when no config
            self.assertFalse(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with(
                "Skipping message from unmapped channel None"
            )

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config')
    def test_handle_room_message_unmapped_room(self, mock_config):
        """Test handle_room_message with unmapped room."""
        self.plugin.matches = MagicMock(return_value=True)

        # Mock config with no matching room
        mock_config.get.return_value = [
            {"id": "!other:matrix.org", "meshtastic_channel": 1}
        ]

        room = MagicMock()
        room.room_id = "!test:matrix.org"  # Not in config
        event = MagicMock()

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return False for unmapped room
            self.assertFalse(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with(
                "Skipping message from unmapped channel None"
            )

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config')
    def test_handle_room_message_missing_packet(self, mock_config):
        """Test handle_room_message with missing embedded packet."""
        self.plugin.matches = MagicMock(return_value=True)

        # Mock config with matching room
        mock_config.get.return_value = [
            {"id": "!test:matrix.org", "meshtastic_channel": 1}
        ]

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()
        event.source = {
            "content": {}  # No meshtastic_packet field
        }

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return False when packet is missing
            self.assertFalse(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with("Missing embedded packet")

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.plugins.mesh_relay_plugin.config')
    def test_handle_room_message_invalid_json_packet(self, mock_config):
        """Test handle_room_message with invalid JSON packet."""
        self.plugin.matches = MagicMock(return_value=True)

        # Mock config with matching room
        mock_config.get.return_value = [
            {"id": "!test:matrix.org", "meshtastic_channel": 1}
        ]

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()
        event.source = {
            "content": {
                "meshtastic_packet": "invalid json"
            }
        }

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return None when JSON parsing fails
            self.assertIsNone(result)

            # Should log error message
            self.plugin.logger.error.assert_called()
            error_call = self.plugin.logger.error.call_args[0][0]
            self.assertIn("Error processing embedded packet", error_call)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
