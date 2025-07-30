#!/usr/bin/env python3
"""
Test suite for Meshtastic utilities edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- Connection failures and timeouts
- Protocol errors and malformed packets
- Hardware disconnection scenarios
- Serial port access issues
- BLE connection instability
- TCP connection drops
- Memory constraints with large node lists
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.meshtastic_utils import (
    connect_meshtastic,
    is_running_as_service,
    on_lost_meshtastic_connection,
    on_meshtastic_message,
    sendTextReply,
    serial_port_exists,
)


class TestMeshtasticUtilsEdgeCases(unittest.TestCase):
    """Test cases for Meshtastic utilities edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.reconnecting = False
        mmrelay.meshtastic_utils.config = None
        mmrelay.meshtastic_utils.matrix_rooms = []

    def tearDown(self):
        """Clean up after each test method."""
        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.reconnecting = False

    def test_serial_port_exists_permission_error(self):
        """Test serial_port_exists when port access is denied."""
        with patch("serial.Serial", side_effect=PermissionError("Permission denied")):
            result = serial_port_exists("/dev/ttyUSB0")
            self.assertFalse(result)

    def test_serial_port_exists_device_not_found(self):
        """Test serial_port_exists when device doesn't exist."""
        with patch("serial.Serial", side_effect=FileNotFoundError("Device not found")):
            result = serial_port_exists("/dev/nonexistent")
            self.assertFalse(result)

    def test_serial_port_exists_device_busy(self):
        """Test serial_port_exists when device is busy."""
        import serial

        with patch("serial.Serial", side_effect=serial.SerialException("Device busy")):
            result = serial_port_exists("/dev/ttyUSB0")
            self.assertFalse(result)

    def test_connect_meshtastic_serial_connection_timeout(self):
        """Test connect_meshtastic with serial connection timeout."""
        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        with patch("mmrelay.meshtastic_utils.serial_port_exists", return_value=True):
            with patch(
                "mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface",
                side_effect=TimeoutError("Connection timeout"),
            ):
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    result = connect_meshtastic(config)
                    self.assertIsNone(result)
                    mock_logger.error.assert_called()

    def test_connect_meshtastic_ble_device_not_found(self):
        """Test connect_meshtastic with BLE device not found."""
        config = {
            "meshtastic": {"connection_type": "ble", "ble_address": "00:11:22:33:44:55"}
        }

        from bleak.exc import BleakError

        with patch(
            "mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface",
            side_effect=ConnectionRefusedError("Device not found"),
        ):
            with patch("time.sleep"):  # Speed up test
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    result = connect_meshtastic(config)
                    self.assertIsNone(result)
                    mock_logger.error.assert_called()

    def test_connect_meshtastic_tcp_connection_refused(self):
        """Test connect_meshtastic with TCP connection refused."""
        config = {"meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}}

        with patch(
            "mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                result = connect_meshtastic(config)
                self.assertIsNone(result)
                mock_logger.error.assert_called()

    def test_connect_meshtastic_invalid_connection_type(self):
        """Test connect_meshtastic with invalid connection type."""
        config = {"meshtastic": {"connection_type": "invalid_type"}}

        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
            result = connect_meshtastic(config)
            self.assertIsNone(result)
            mock_logger.error.assert_called()

    def test_connect_meshtastic_exponential_backoff_max_retries(self):
        """Test connect_meshtastic exponential backoff reaching maximum retries."""
        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        with patch("mmrelay.meshtastic_utils.serial_port_exists", return_value=True):
            with patch(
                "mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface",
                side_effect=MemoryError("Out of memory"),
            ):
                with patch("time.sleep"):  # Speed up test
                    with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                        result = connect_meshtastic(config)
                        self.assertIsNone(result)
                        # Should log error for critical failure
                        mock_logger.error.assert_called()

    def test_on_meshtastic_message_malformed_packet(self):
        """Test on_meshtastic_message with malformed packet data."""
        malformed_packets = [
            {},  # Empty packet
            {"decoded": None},  # None decoded
            {"decoded": {"text": None}},  # None text
            {"fromId": None},  # None fromId
            {"channel": "invalid"},  # Invalid channel type
        ]

        for packet in malformed_packets:
            with self.subTest(packet=packet):
                mock_interface = MagicMock()
                with patch("mmrelay.meshtastic_utils.logger"):
                    # Should handle malformed packets gracefully
                    on_meshtastic_message(packet, mock_interface)

    def test_on_meshtastic_message_plugin_processing_failure(self):
        """Test on_meshtastic_message when plugin processing fails."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        mock_interface = MagicMock()

        with patch("mmrelay.plugin_loader.load_plugins") as mock_load_plugins:
            mock_plugin = MagicMock()
            mock_plugin.handle_meshtastic_message.side_effect = Exception(
                "Plugin failed"
            )
            mock_load_plugins.return_value = [mock_plugin]

            with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                on_meshtastic_message(packet, mock_interface)
                mock_logger.error.assert_called()

    def test_on_meshtastic_message_matrix_relay_failure(self):
        """Test on_meshtastic_message when Matrix relay fails."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
            "to": 4294967295,  # BROADCAST_NUM
        }

        mock_interface = MagicMock()

        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.matrix_rooms = [
            {"id": "!room:matrix.org", "meshtastic_channel": 0}
        ]

        with patch("mmrelay.plugin_loader.load_plugins", return_value=[]):
            with patch(
                "mmrelay.matrix_utils.matrix_relay",
                side_effect=Exception("Matrix relay failed"),
            ):
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    on_meshtastic_message(packet, mock_interface)
                    mock_logger.error.assert_called()

    def test_on_meshtastic_message_database_error(self):
        """Test on_meshtastic_message when database operations fail."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        mock_interface = MagicMock()

        with patch(
            "mmrelay.db_utils.get_longname", side_effect=Exception("Database error")
        ):
            with patch("mmrelay.meshtastic_utils.logger"):
                on_meshtastic_message(packet, mock_interface)
                # Should handle database errors gracefully

    def test_on_lost_meshtastic_connection_reconnection_failure(self):
        """Test on_lost_meshtastic_connection when reconnection fails."""
        mock_interface = MagicMock()

        with patch("mmrelay.meshtastic_utils.connect_meshtastic", return_value=None):
            with patch("time.sleep"):  # Speed up test
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    on_lost_meshtastic_connection(mock_interface)
                    mock_logger.error.assert_called()

    def test_on_lost_meshtastic_connection_detection_source_edge_cases(self):
        """Test on_lost_meshtastic_connection with various detection sources."""
        mock_interface = MagicMock()

        detection_sources = [
            "unknown_source",
            None,
            123,  # Invalid type
            "",  # Empty string
        ]

        for source in detection_sources:
            with self.subTest(detection_source=source):
                with patch(
                    "mmrelay.meshtastic_utils.connect_meshtastic",
                    return_value=MagicMock(),
                ):
                    with patch("time.sleep"):
                        # Should handle various detection sources gracefully
                        on_lost_meshtastic_connection(
                            mock_interface, detection_source=source
                        )

    def test_sendTextReply_no_client(self):
        """Test sendTextReply when no Meshtastic client is available."""
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None

        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
            result = sendTextReply(None, "test message", 12345)
            self.assertIsNone(result)
            mock_logger.error.assert_called()

    def test_sendTextReply_client_send_failure(self):
        """Test sendTextReply when client send operation fails."""
        mock_client = MagicMock()
        mock_client._sendPacket.side_effect = Exception("Send failed")

        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = mock_client

        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
            result = sendTextReply(mock_client, "test message", 12345)
            self.assertIsNone(result)
            mock_logger.error.assert_called()

    def test_is_running_as_service_detection_failure(self):
        """Test is_running_as_service when detection methods fail."""
        with patch("os.getppid", side_effect=OSError("Cannot get parent PID")):
            with patch(
                "psutil.Process", side_effect=Exception("Process info unavailable")
            ):
                # Should handle detection failures gracefully
                result = is_running_as_service()
                self.assertIsInstance(result, bool)

    def test_connect_meshtastic_concurrent_access(self):
        """Test connect_meshtastic with concurrent access scenarios."""
        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.reconnecting = True  # Simulate ongoing reconnection

        result = connect_meshtastic(config)
        # Should handle concurrent access gracefully
        self.assertIsNone(result)

    def test_connect_meshtastic_memory_constraint(self):
        """Test connect_meshtastic under memory constraints."""
        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        with patch("mmrelay.meshtastic_utils.serial_port_exists", return_value=True):
            with patch(
                "mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface",
                side_effect=MemoryError("Out of memory"),
            ):
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    result = connect_meshtastic(config)
                    self.assertIsNone(result)
                    mock_logger.error.assert_called()

    def test_on_meshtastic_message_large_node_list(self):
        """Test on_meshtastic_message with very large node lists."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        # Create a mock interface with a large node list
        mock_interface = MagicMock()
        large_nodes = {}
        for i in range(10000):  # Large number of nodes
            large_nodes[f"node_{i}"] = {
                "user": {
                    "id": f"!{i:08x}",
                    "longName": f"Node {i}",
                    "shortName": f"N{i}",
                }
            }
        mock_interface.nodes = large_nodes

        with patch("mmrelay.meshtastic_utils.logger"):
            # Should handle large node lists without crashing
            on_meshtastic_message(packet, mock_interface)

    def test_connect_meshtastic_config_validation_edge_cases(self):
        """Test connect_meshtastic with various invalid configurations."""
        invalid_configs = [
            None,  # None config
            {},  # Empty config
            {"meshtastic": None},  # None meshtastic section
            {"meshtastic": {}},  # Empty meshtastic section
            {"meshtastic": {"connection_type": None}},  # None connection type
        ]

        for config in invalid_configs:
            with self.subTest(config=config):
                with patch("mmrelay.meshtastic_utils.logger"):
                    result = connect_meshtastic(config)
                    # Should handle invalid configs gracefully
                    self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
