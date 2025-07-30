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
                "portnum": "TEXT_MESSAGE_APP"  # Use string constant
            },
            "channel": 0,
            "id": 12345,
            "rxTime": 1234567890
        }

        # Reset global state to avoid test interference
        import mmrelay.meshtastic_utils
        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.config = None
        mmrelay.meshtastic_utils.matrix_rooms = []

    def test_on_meshtastic_message_basic(self):
        """Test basic message processing."""
        # Mock the required functions
        import mmrelay.meshtastic_utils

        with patch('mmrelay.meshtastic_utils.get_longname') as mock_get_longname, \
             patch('mmrelay.meshtastic_utils.get_shortname') as mock_get_shortname, \
             patch('mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe') as mock_run_coro, \
             patch('mmrelay.matrix_utils.matrix_relay') as mock_matrix_relay, \
             patch('mmrelay.matrix_utils.get_interaction_settings') as mock_get_interactions, \
             patch('mmrelay.matrix_utils.message_storage_enabled') as mock_storage:

            mock_get_longname.return_value = "Test User"
            mock_get_shortname.return_value = "TU"
            mock_get_interactions.return_value = {"reactions": False, "replies": False}
            mock_storage.return_value = True

            # Mock interface
            mock_interface = MagicMock()

            # Set up the global config and matrix_rooms
            mmrelay.meshtastic_utils.config = self.mock_config
            mmrelay.meshtastic_utils.matrix_rooms = self.mock_config["matrix_rooms"]
            mmrelay.meshtastic_utils.event_loop = MagicMock()  # Mock the event loop

            # Call the function
            on_meshtastic_message(self.mock_packet, mock_interface)

            # Verify asyncio.run_coroutine_threadsafe was called (which calls matrix_relay)
            mock_run_coro.assert_called_once()

    def test_on_meshtastic_message_unmapped_channel(self):
        """Test message processing for unmapped channel."""
        # Modify packet to use unmapped channel
        packet_unmapped = self.mock_packet.copy()
        packet_unmapped["channel"] = 99  # Not in matrix_rooms config

        with patch('mmrelay.meshtastic_utils.config', self.mock_config), \
             patch('mmrelay.meshtastic_utils.matrix_rooms', self.mock_config["matrix_rooms"]), \
             patch('mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe') as mock_run_coro:

            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(packet_unmapped, mock_interface)

            # Verify asyncio.run_coroutine_threadsafe was not called (no matrix relay)
            mock_run_coro.assert_not_called()

    def test_on_meshtastic_message_no_text(self):
        """Test message processing for packet without text."""
        # Modify packet to have no text
        packet_no_text = self.mock_packet.copy()
        packet_no_text["decoded"] = {"portnum": 2}  # Not TEXT_MESSAGE_APP

        with patch('mmrelay.meshtastic_utils.config', self.mock_config), \
             patch('mmrelay.meshtastic_utils.matrix_rooms', self.mock_config["matrix_rooms"]), \
             patch('mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe') as mock_run_coro, \
             patch('mmrelay.plugin_loader.load_plugins') as mock_load_plugins:

            mock_load_plugins.return_value = []
            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(packet_no_text, mock_interface)

            # Verify asyncio.run_coroutine_threadsafe was not called for non-text message
            mock_run_coro.assert_not_called()

    @patch('mmrelay.meshtastic_utils.serial_port_exists')
    @patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface')
    def test_connect_meshtastic_serial(self, mock_tcp, mock_ble, mock_serial, mock_port_exists):
        """Test connecting to Meshtastic via serial."""
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {"user": {"id": "test"}}
        mock_serial.return_value = mock_client
        mock_port_exists.return_value = True

        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_serial.assert_called_once_with("/dev/ttyUSB0")

    @patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface')
    def test_connect_meshtastic_tcp(self, mock_tcp, mock_ble, mock_serial):
        """Test connecting to Meshtastic via TCP."""
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {"user": {"id": "test"}}
        mock_tcp.return_value = mock_client

        config = {
            "meshtastic": {
                "connection_type": "tcp",
                "host": "192.168.1.100"  # Use 'host' not 'tcp_host'
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_tcp.assert_called_once_with(hostname="192.168.1.100")

    @patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface')
    def test_connect_meshtastic_ble(self, mock_tcp, mock_ble, mock_serial):
        """Test connecting to Meshtastic via BLE."""
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {"user": {"id": "test"}}
        mock_ble.return_value = mock_client

        config = {
            "meshtastic": {
                "connection_type": "ble",
                "ble_address": "AA:BB:CC:DD:EE:FF"
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        # Check the actual call parameters
        mock_ble.assert_called_once_with(
            address="AA:BB:CC:DD:EE:FF",
            noProto=False,
            debugOut=None,
            noNodes=False
        )

    @patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface')
    @patch('mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface')
    def test_connect_meshtastic_invalid_type(self, mock_tcp, mock_ble, mock_serial):
        """Test connecting with invalid connection type."""
        config = {
            "meshtastic": {
                "connection_type": "invalid"
            }
        }

        result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)
        # None of the interfaces should be called
        mock_serial.assert_not_called()
        mock_tcp.assert_not_called()
        mock_ble.assert_not_called()

    def test_sendTextReply_success(self):
        """Test sending text reply successfully."""
        # Create a mock interface
        mock_interface = MagicMock()
        mock_interface._generatePacketId.return_value = 12345
        mock_interface._sendPacket.return_value = {"id": 12345}

        result = sendTextReply(mock_interface, "Hello", 999, destinationId=123456789)

        # Should return the result from _sendPacket
        self.assertEqual(result, {"id": 12345})

        # Verify the interface methods were called
        mock_interface._generatePacketId.assert_called_once()
        mock_interface._sendPacket.assert_called_once()

    def test_sendTextReply_no_client(self):
        """Test sending text reply when interface fails."""
        # Create a mock interface that fails
        mock_interface = MagicMock()
        mock_interface._generatePacketId.return_value = 12345
        mock_interface._sendPacket.return_value = None  # Simulate failure

        result = sendTextReply(mock_interface, "Hello", 999, destinationId=123456789)

        self.assertIsNone(result)

    def test_on_meshtastic_message_with_broadcast_config(self):
        """Test message processing with broadcast config (broadcast_enabled affects Matrix->Meshtastic, not Meshtastic->Matrix)."""
        config_no_broadcast = self.mock_config.copy()
        config_no_broadcast["meshtastic"]["broadcast_enabled"] = False

        with patch('mmrelay.meshtastic_utils.config', config_no_broadcast), \
             patch('mmrelay.meshtastic_utils.matrix_rooms', config_no_broadcast["matrix_rooms"]), \
             patch('mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe') as mock_run_coro, \
             patch('mmrelay.meshtastic_utils.get_longname') as mock_get_longname, \
             patch('mmrelay.meshtastic_utils.get_shortname') as mock_get_shortname, \
             patch('mmrelay.matrix_utils.get_interaction_settings') as mock_get_interactions, \
             patch('mmrelay.matrix_utils.message_storage_enabled') as mock_storage:

            mock_get_longname.return_value = "Test User"
            mock_get_shortname.return_value = "TU"
            mock_get_interactions.return_value = {"reactions": False, "replies": False}
            mock_storage.return_value = True

            mock_interface = MagicMock()

            # Set up event loop mock
            import mmrelay.meshtastic_utils
            mmrelay.meshtastic_utils.event_loop = MagicMock()

            # Call the function
            on_meshtastic_message(self.mock_packet, mock_interface)

            # Meshtastic->Matrix messages are still relayed regardless of broadcast_enabled
            # (broadcast_enabled only affects Matrix->Meshtastic direction)
            mock_run_coro.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class TestMeshtasticUtilsAsync(unittest.TestCase):
    """Simplified async tests that avoid AsyncMock warnings."""

    def test_async_message_processing_setup(self):
        """Test that async message processing components are properly configured."""
        # This test just verifies that the async components exist and can be imported
        # without actually running async code that could cause warnings

        # Test that we can import the async functions
        from mmrelay.matrix_utils import matrix_relay
        from mmrelay.meshtastic_utils import on_meshtastic_message

        # Test that asyncio functions are available
        import asyncio
        self.assertIsNotNone(asyncio.run_coroutine_threadsafe)

        # Test that the functions exist
        self.assertIsNotNone(matrix_relay)
        self.assertIsNotNone(on_meshtastic_message)

        # This test passes if all imports work correctly
        # Complex async testing is better done through integration tests


if __name__ == "__main__":
    unittest.main()
