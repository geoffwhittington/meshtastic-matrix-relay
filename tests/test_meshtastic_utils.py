#!/usr/bin/env python3
"""
Test suite for Meshtastic utilities in MMRelay.

Tests the Meshtastic client functionality including:
- Message processing and relay to Matrix
- Connection management (serial, TCP, BLE)
- Node information handling
- Packet parsing and validation
- Error handling and reconnection logic
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.meshtastic_utils import (
    connect_meshtastic,
    on_meshtastic_message,
    sendTextReply,
)


class TestMeshtasticUtils(unittest.TestCase):
    """Test cases for Meshtastic utilities."""

    def setUp(self):
        """Set up test environment."""
        # Mock configuration
        self.mock_config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "broadcast_enabled": True,
                "meshnet_name": "test_mesh"
            },
            "matrix_rooms": [
                {"id": "!room1:matrix.org", "meshtastic_channel": 0},
                {"id": "!room2:matrix.org", "meshtastic_channel": 1}
            ]
        }

        # Mock packet data
        self.mock_packet = {
            "from": 123456789,
            "to": 987654321,
            "decoded": {
                "text": "Hello from mesh",
                "portnum": 1  # TEXT_MESSAGE_APP
            },
            "channel": 0,
            "id": 12345,
            "rxTime": 1234567890
        }

    @patch('mmrelay.meshtastic_utils.matrix_relay')
    @patch('mmrelay.meshtastic_utils.get_longname')
    @patch('mmrelay.meshtastic_utils.get_shortname')
    def test_on_meshtastic_message_basic(self, mock_get_shortname, mock_get_longname, mock_matrix_relay):
        """Test basic message processing."""
        mock_get_longname.return_value = "Test User"
        mock_get_shortname.return_value = "TU"

        # Mock interface
        mock_interface = MagicMock()

        # Set up the global config and matrix_rooms
        import mmrelay.meshtastic_utils
        mmrelay.meshtastic_utils.config = self.mock_config
        mmrelay.meshtastic_utils.matrix_rooms = self.mock_config["matrix_rooms"]

        # Call the function
        on_meshtastic_message(self.mock_packet, mock_interface)

        # Verify matrix_relay was called
        mock_matrix_relay.assert_called_once()

    def test_on_meshtastic_message_unmapped_channel(self):
        """Test message processing for unmapped channel."""
        # Modify packet to use unmapped channel
        packet_unmapped = self.mock_packet.copy()
        packet_unmapped["channel"] = 99  # Not in matrix_rooms config

        with patch('mmrelay.meshtastic_utils.config', self.mock_config), \
             patch('mmrelay.meshtastic_utils.matrix_rooms', self.mock_config["matrix_rooms"]), \
             patch('mmrelay.meshtastic_utils.matrix_relay') as mock_matrix_relay:

            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(packet_unmapped, mock_interface)

            # Verify matrix_relay was not called
            mock_matrix_relay.assert_not_called()

    def test_on_meshtastic_message_no_text(self):
        """Test message processing for packet without text."""
        # Modify packet to have no text
        packet_no_text = self.mock_packet.copy()
        packet_no_text["decoded"] = {"portnum": 2}  # Not TEXT_MESSAGE_APP

        with patch('mmrelay.meshtastic_utils.config', self.mock_config), \
             patch('mmrelay.meshtastic_utils.matrix_rooms', self.mock_config["matrix_rooms"]), \
             patch('mmrelay.meshtastic_utils.matrix_relay') as mock_matrix_relay, \
             patch('mmrelay.meshtastic_utils.plugin_loader') as mock_plugin_loader:

            mock_plugin_loader.sorted_active_plugins = []
            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(packet_no_text, mock_interface)

            # Verify matrix_relay was not called for non-text message
            mock_matrix_relay.assert_not_called()

    @patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface')
    def test_connect_meshtastic_serial(self, mock_serial_interface):
        """Test connecting to Meshtastic via serial."""
        mock_client = MagicMock()
        mock_serial_interface.return_value = mock_client

        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_serial_interface.assert_called_once_with("/dev/ttyUSB0")

    @patch('mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface')
    def test_connect_meshtastic_tcp(self, mock_tcp_interface):
        """Test connecting to Meshtastic via TCP."""
        mock_client = MagicMock()
        mock_tcp_interface.return_value = mock_client

        config = {
            "meshtastic": {
                "connection_type": "tcp",
                "tcp_host": "192.168.1.100",
                "tcp_port": 4403
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_tcp_interface.assert_called_once_with("192.168.1.100", 4403)

    @patch('mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface')
    def test_connect_meshtastic_ble(self, mock_ble_interface):
        """Test connecting to Meshtastic via BLE."""
        mock_client = MagicMock()
        mock_ble_interface.return_value = mock_client

        config = {
            "meshtastic": {
                "connection_type": "ble",
                "ble_address": "AA:BB:CC:DD:EE:FF"
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_ble_interface.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    def test_connect_meshtastic_invalid_type(self):
        """Test connecting with invalid connection type."""
        config = {
            "meshtastic": {
                "connection_type": "invalid"
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)

    @patch('mmrelay.meshtastic_utils.meshtastic_client')
    def test_sendTextReply_success(self, mock_client):
        """Test sending text reply successfully."""
        mock_client.sendText.return_value = {"id": 12345}

        result = sendTextReply("Hello", 0, 123456789)

        self.assertEqual(result, {"id": 12345})
        mock_client.sendText.assert_called_once_with(
            "Hello",
            destinationId=123456789,
            channelIndex=0
        )

    @patch('mmrelay.meshtastic_utils.meshtastic_client')
    def test_sendTextReply_no_client(self, mock_client):
        """Test sending text reply when no client is available."""
        mock_client = None

        with patch('mmrelay.meshtastic_utils.meshtastic_client', None):
            result = sendTextReply("Hello", 0, 123456789)

        self.assertIsNone(result)

    def test_on_meshtastic_message_broadcast_disabled(self):
        """Test message processing when broadcast is disabled."""
        config_no_broadcast = self.mock_config.copy()
        config_no_broadcast["meshtastic"]["broadcast_enabled"] = False

        with patch('mmrelay.meshtastic_utils.config', config_no_broadcast), \
             patch('mmrelay.meshtastic_utils.matrix_rooms', config_no_broadcast["matrix_rooms"]), \
             patch('mmrelay.meshtastic_utils.matrix_relay') as mock_matrix_relay:

            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(self.mock_packet, mock_interface)

            # Verify matrix_relay was not called when broadcast is disabled
            mock_matrix_relay.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class TestMeshtasticUtils(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.mock_interface = MagicMock()
        self.mock_interface.myInfo.my_node_num = 12345
        self.mock_packet = {
            "fromId": "!fromId",
            "to": "^all",
            "decoded": {"text": "Hello, world!", "portnum": "TEXT_MESSAGE_APP"},
            "channel": 0,
            "id": "message_id",
        }
        self.config = {
            "meshtastic": {
                "meshnet_name": "test_mesh",
                "message_interactions": {"reactions": False, "replies": False},
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
        }

    def tearDown(self):
        self.loop.close()

    @patch("mmrelay.matrix_utils.matrix_relay", new_callable=AsyncMock)
    @patch("mmrelay.meshtastic_utils.get_longname")
    @patch("mmrelay.meshtastic_utils.get_shortname")
    @patch("mmrelay.plugin_loader.load_plugins")
    @patch("mmrelay.matrix_utils.get_interaction_settings")
    @patch("mmrelay.meshtastic_utils.logger")
    def test_on_meshtastic_message_simple_text(
        self,
        mock_logger,
        mock_get_interaction_settings,
        mock_load_plugins,
        mock_get_shortname,
        mock_get_longname,
        mock_matrix_relay,
    ):
        mock_load_plugins.return_value = []
        mock_get_longname.return_value = "longname"
        mock_get_shortname.return_value = "shortname"
        mock_get_interaction_settings.return_value = {
            "reactions": False,
            "replies": False,
        }

        from meshtastic import mesh_interface

        self.mock_packet["to"] = mesh_interface.BROADCAST_NUM

        with patch("mmrelay.meshtastic_utils.config", self.config), patch(
            "mmrelay.meshtastic_utils.event_loop", self.loop
        ), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.config["matrix_rooms"]
        ):
            # Run the function
            on_meshtastic_message(self.mock_packet, self.mock_interface)

            # Assert that the message was relayed
            self.loop.run_until_complete(asyncio.sleep(0.1))
            mock_matrix_relay.assert_called_once()
            call_args = mock_matrix_relay.call_args[0]
            self.assertIn("Hello, world!", call_args["text"])

    @patch("mmrelay.matrix_utils.matrix_relay", new_callable=AsyncMock)
    @patch("mmrelay.meshtastic_utils.logger")
    def test_on_meshtastic_message_unmapped_channel(self, mock_logger, mock_matrix_relay):
        self.mock_packet["channel"] = 1
        with patch("mmrelay.meshtastic_utils.config", self.config), patch(
            "mmrelay.meshtastic_utils.event_loop", self.loop
        ), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.config["matrix_rooms"]
        ):
            # Run the function
            on_meshtastic_message(self.mock_packet, self.mock_interface)

            # Assert that the message was not relayed
            self.loop.run_until_complete(asyncio.sleep(0.1))
            mock_matrix_relay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
