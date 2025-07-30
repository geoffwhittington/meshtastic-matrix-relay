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
        """
        Initializes the Plugin instance and mocks dependencies for each test.

        Sets up a Plugin object, replaces its logger with a mock, and mocks the strip_raw method to return its input unchanged.
        """
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()

        # Mock the strip_raw method from base plugin
        self.plugin.strip_raw = MagicMock(side_effect=lambda x: x)

    def test_plugin_name(self):
        """
        Test that the plugin's name attribute is set to "mesh_relay".
        """
        self.assertEqual(self.plugin.plugin_name, "mesh_relay")

    def test_max_data_rows_per_node(self):
        """
        Verify that the plugin's maximum data rows per node is set to 50.
        """
        self.assertEqual(self.plugin.max_data_rows_per_node, 50)

    def test_get_matrix_commands(self):
        """
        Test that get_matrix_commands returns an empty list.
        """
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, [])

    def test_get_mesh_commands(self):
        """
        Test that get_mesh_commands returns an empty list.
        """
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, [])

    def test_normalize_dict_input(self):
        """
        Tests that the normalize method correctly processes a dictionary input by calling strip_raw and returning the unchanged dictionary.
        """
        input_dict = {"decoded": {"text": "test message"}}

        result = self.plugin.normalize(input_dict)

        # Should call strip_raw and return the result
        self.plugin.strip_raw.assert_called_once_with(input_dict)
        self.assertEqual(result, input_dict)

    def test_normalize_json_string_input(self):
        """
        Test that the normalize method correctly parses a JSON string input and returns the expected dictionary.

        Verifies that the input JSON string is parsed, passed to strip_raw, and the resulting dictionary matches the expected output.
        """
        input_json = '{"decoded": {"text": "test message"}}'
        expected_dict = {"decoded": {"text": "test message"}}

        result = self.plugin.normalize(input_json)

        # Should parse JSON and call strip_raw
        self.plugin.strip_raw.assert_called_once_with(expected_dict)
        self.assertEqual(result, expected_dict)

    def test_normalize_plain_string_input(self):
        """
        Test that the normalize method wraps a plain string input in a dictionary under the 'decoded.text' key.
        """
        input_string = "plain text message"
        expected_dict = {"decoded": {"text": "plain text message"}}

        result = self.plugin.normalize(input_string)

        # Should wrap in TEXT_MESSAGE_APP format
        self.plugin.strip_raw.assert_called_once_with(expected_dict)
        self.assertEqual(result, expected_dict)

    def test_normalize_invalid_json_input(self):
        """
        Test that the normalize method treats an invalid JSON string as plain text.

        Verifies that when given a string that cannot be parsed as JSON, the normalize method wraps it in a dictionary under the "decoded" key and passes it to strip_raw.
        """
        input_string = '{"invalid": json}'
        expected_dict = {"decoded": {"text": '{"invalid": json}'}}

        result = self.plugin.normalize(input_string)

        # Should treat as plain string when JSON parsing fails
        self.plugin.strip_raw.assert_called_once_with(expected_dict)
        self.assertEqual(result, expected_dict)

    def test_process_packet_without_payload(self):
        """
        Test that the process method returns the original packet unchanged when no binary payload is present.
        """
        packet = {"decoded": {"text": "test message"}}

        result = self.plugin.process(packet)

        # Should normalize but not modify payload
        self.assertEqual(result, packet)

    def test_process_packet_with_binary_payload(self):
        """
        Test that the process method base64-encodes binary payloads in a packet.

        Verifies that when a packet contains a binary payload, the process method encodes it as a base64 UTF-8 string in the output.
        """
        binary_data = b"binary payload data"
        packet = {"decoded": {"payload": binary_data}}

        result = self.plugin.process(packet)

        # Should encode binary payload as base64
        expected_payload = base64.b64encode(binary_data).decode("utf-8")
        self.assertEqual(result["decoded"]["payload"], expected_payload)

    def test_process_packet_with_string_payload(self):
        """
        Test that the process method leaves string payloads in the packet unchanged.
        """
        packet = {"decoded": {"payload": "string payload"}}

        result = self.plugin.process(packet)

        # Should not modify string payload
        self.assertEqual(result["decoded"]["payload"], "string payload")

    def test_matches_valid_radio_packet_message(self):
        """
        Test that the matches method returns True for an event containing a valid radio packet message.
        """
        event = MagicMock()
        event.source = {"content": {"body": "Processed TEXT_MESSAGE_APP radio packet"}}

        result = self.plugin.matches(event)

        self.assertTrue(result)

    def test_matches_invalid_message_format(self):
        """
        Test that the matches method returns False when the event body is not a valid radio packet message.
        """
        event = MagicMock()
        event.source = {"content": {"body": "This is not a radio packet message"}}

        result = self.plugin.matches(event)

        self.assertFalse(result)

    def test_matches_missing_content(self):
        """
        Test that the matches method returns False when the event has no content.
        """
        event = MagicMock()
        event.source = {}

        result = self.plugin.matches(event)

        self.assertFalse(result)

    def test_matches_non_string_body(self):
        """
        Test that the matches method returns False when the event body is not a string.
        """
        event = MagicMock()
        event.source = {"content": {"body": 123}}  # Non-string body

        result = self.plugin.matches(event)

        self.assertFalse(result)

    @patch("mmrelay.plugins.mesh_relay_plugin.config", None)
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_meshtastic_message_no_config(self, mock_connect):
        """
        Test that handle_meshtastic_message returns None and does not send a Matrix message when no configuration is present.
        """
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"},
            "channel": 0,
        }

        async def run_test():
            """
            Asynchronously tests that `handle_meshtastic_message` returns None and does not send a Matrix message when no configuration is present.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return None when no config
            self.assertIsNone(result)

            # Should not send any Matrix messages
            mock_matrix_client.room_send.assert_not_called()

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.plugins.mesh_relay_plugin.config")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_meshtastic_message_unmapped_channel(
        self, mock_connect, mock_config
    ):
        """
        Test that handle_meshtastic_message returns None and does not send a Matrix message when the packet's channel is not mapped in the configuration.
        """
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        # Mock config with no matching channel
        mock_config.get.return_value = [
            {"meshtastic_channel": 1, "id": "!room1:matrix.org"}
        ]

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"},
            "channel": 0,  # Channel 0 not mapped
        }

        async def run_test():
            """
            Asynchronously tests that handle_meshtastic_message returns None and skips sending a Matrix message when the channel is not mapped in the configuration.
            """
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

    @patch("mmrelay.plugins.mesh_relay_plugin.config")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_meshtastic_message_mapped_channel(self, mock_connect, mock_config):
        """
        Test that handle_meshtastic_message sends a Matrix message when the packet's channel is mapped in the configuration.

        Verifies that the correct Matrix room, message type, and content are used, and that the function returns False to allow further processing by other plugins.
        """
        mock_matrix_client = AsyncMock()
        mock_connect.return_value = mock_matrix_client

        # Mock config with matching channel
        mock_config.get.return_value = [
            {"meshtastic_channel": 0, "id": "!room1:matrix.org"}
        ]

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "test"},
            "channel": 0,
        }

        async def run_test():
            """
            Asynchronously tests that a Meshtastic message on a mapped channel triggers correct Matrix message sending.

            Verifies that the plugin returns False to allow further processing, sends a Matrix message to the expected room with the correct message type and content, and includes the processed Meshtastic packet in the message body.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return False (allows other plugins to process)
            self.assertFalse(result)

            # Should send Matrix message
            mock_matrix_client.room_send.assert_called_once()
            call_args = mock_matrix_client.room_send.call_args

            self.assertEqual(call_args.kwargs["room_id"], "!room1:matrix.org")
            self.assertEqual(call_args.kwargs["message_type"], "m.room.message")

            content = call_args.kwargs["content"]
            self.assertEqual(content["msgtype"], "m.text")
            self.assertTrue(content["mmrelay_suppress"])
            self.assertIn("meshtastic_packet", content)
            self.assertEqual(content["body"], "Processed TEXT_MESSAGE_APP radio packet")

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.plugins.mesh_relay_plugin.config")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_meshtastic_message_no_channel_field(
        self, mock_connect, mock_config
    ):
        """
        Test that handle_meshtastic_message correctly defaults to channel 0 when the packet lacks a channel field.

        Verifies that a Matrix message is sent to the room mapped to channel 0 and that the method returns False.
        """
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
            """
            Runs an asynchronous test for handling a Meshtastic message with a missing channel field, verifying that the plugin defaults to channel 0 and sends a Matrix message.

            Returns:
                None
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return False and send message (channel defaults to 0)
            self.assertFalse(result)
            mock_matrix_client.room_send.assert_called_once()

        import asyncio

        asyncio.run(run_test())

    def test_handle_room_message_no_match(self):
        """
        Test that handle_room_message returns False when the event does not match plugin criteria.
        """
        self.plugin.matches = MagicMock(return_value=False)

        room = MagicMock()
        event = MagicMock()

        async def run_test():
            """
            Asynchronously tests that `handle_room_message` returns False and calls `matches` with the given event.
            """
            result = await self.plugin.handle_room_message(room, event, "full_message")
            self.assertFalse(result)
            self.plugin.matches.assert_called_once_with(event)

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.plugins.mesh_relay_plugin.config", None)
    def test_handle_room_message_no_config(self):
        """
        Test that handle_room_message returns False and logs a debug message when no configuration is present.
        """
        self.plugin.matches = MagicMock(return_value=True)

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()

        async def run_test():
            """
            Asynchronously tests that handle_room_message returns False and logs a debug message when no configuration is present.
            """
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return False when no config
            self.assertFalse(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with(
                "Skipping message from unmapped channel None"
            )

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.plugins.mesh_relay_plugin.config")
    def test_handle_room_message_unmapped_room(self, mock_config):
        """
        Test that handle_room_message returns False and logs a debug message when the room is not mapped in the configuration.
        """
        self.plugin.matches = MagicMock(return_value=True)

        # Mock config with no matching room
        mock_config.get.return_value = [
            {"id": "!other:matrix.org", "meshtastic_channel": 1}
        ]

        room = MagicMock()
        room.room_id = "!test:matrix.org"  # Not in config
        event = MagicMock()

        async def run_test():
            """
            Runs an asynchronous test to verify that `handle_room_message` returns False and logs a debug message when called with an unmapped room.
            """
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return False for unmapped room
            self.assertFalse(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with(
                "Skipping message from unmapped channel None"
            )

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.plugins.mesh_relay_plugin.config")
    def test_handle_room_message_missing_packet(self, mock_config):
        """
        Test that handle_room_message returns False and logs a debug message when the embedded packet is missing from the event.
        """
        self.plugin.matches = MagicMock(return_value=True)

        # Mock config with matching room
        mock_config.get.return_value = [
            {"id": "!test:matrix.org", "meshtastic_channel": 1}
        ]

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()
        event.source = {"content": {}}  # No meshtastic_packet field

        async def run_test():
            """
            Runs the test for handling a Matrix room message when the embedded packet is missing.

            Asserts that the handler returns False and logs a debug message indicating the missing packet.
            """
            result = await self.plugin.handle_room_message(room, event, "full_message")

            # Should return False when packet is missing
            self.assertFalse(result)

            # Should log debug message
            self.plugin.logger.debug.assert_called_with("Missing embedded packet")

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.plugins.mesh_relay_plugin.config")
    def test_handle_room_message_invalid_json_packet(self, mock_config):
        """
        Test that handle_room_message returns None and logs an error when the embedded packet contains invalid JSON.
        """
        self.plugin.matches = MagicMock(return_value=True)

        # Mock config with matching room
        mock_config.get.return_value = [
            {"id": "!test:matrix.org", "meshtastic_channel": 1}
        ]

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()
        event.source = {"content": {"meshtastic_packet": "invalid json"}}

        async def run_test():
            """
            Asynchronously tests that `handle_room_message` returns None and logs an error when embedded packet JSON parsing fails.
            """
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
