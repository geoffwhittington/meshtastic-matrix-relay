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
        """
        Reset global state in mmrelay.meshtastic_utils before each test to ensure test isolation.
        """
        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.reconnecting = False
        mmrelay.meshtastic_utils.config = None
        mmrelay.meshtastic_utils.matrix_rooms = []
        mmrelay.meshtastic_utils.shutting_down = False
        mmrelay.meshtastic_utils.event_loop = None
        mmrelay.meshtastic_utils.reconnect_task = None
        mmrelay.meshtastic_utils.subscribed_to_messages = False
        mmrelay.meshtastic_utils.subscribed_to_connection_lost = False

    def tearDown(self):
        """
        Reset global state variables in mmrelay.meshtastic_utils after each test to ensure test isolation.
        """
        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.reconnecting = False
        mmrelay.meshtastic_utils.config = None
        mmrelay.meshtastic_utils.matrix_rooms = []
        mmrelay.meshtastic_utils.shutting_down = False
        mmrelay.meshtastic_utils.event_loop = None
        mmrelay.meshtastic_utils.reconnect_task = None
        mmrelay.meshtastic_utils.subscribed_to_messages = False
        mmrelay.meshtastic_utils.subscribed_to_connection_lost = False

    def test_serial_port_exists_permission_error(self):
        """
        Test that serial_port_exists returns False when a PermissionError occurs due to denied access to the serial port.
        """
        with patch("serial.Serial", side_effect=PermissionError("Permission denied")):
            result = serial_port_exists("/dev/ttyUSB0")
            self.assertFalse(result)

    def test_serial_port_exists_device_not_found(self):
        """
        Test that serial_port_exists returns False when the specified device is not found.
        """
        with patch("serial.Serial", side_effect=FileNotFoundError("Device not found")):
            result = serial_port_exists("/dev/nonexistent")
            self.assertFalse(result)

    def test_serial_port_exists_device_busy(self):
        """
        Test that serial_port_exists returns False when the serial device is busy.

        Simulates a busy device by patching serial.Serial to raise SerialException.
        """
        import serial

        with patch("serial.Serial", side_effect=serial.SerialException("Device busy")):
            result = serial_port_exists("/dev/ttyUSB0")
            self.assertFalse(result)

    def test_connect_meshtastic_serial_connection_timeout(self):
        """
        Verifies that connect_meshtastic returns None and logs an error when a serial connection attempt times out.
        """
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
        """
        Test that connect_meshtastic returns None and logs an error when a BLE device is not found.

        Simulates a BLE connection attempt where the device is unavailable, verifying graceful failure and error logging.
        """
        config = {
            "meshtastic": {"connection_type": "ble", "ble_address": "00:11:22:33:44:55"}
        }

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
        """
        Verifies that connect_meshtastic returns None and logs an error when a TCP connection is refused.
        """
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
        """
        Test that connect_meshtastic returns None and logs an error when given an invalid connection type in the configuration.
        """
        config = {"meshtastic": {"connection_type": "invalid_type"}}

        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
            result = connect_meshtastic(config)
            self.assertIsNone(result)
            mock_logger.error.assert_called()

    def test_connect_meshtastic_exponential_backoff_max_retries(self):
        """
        Verify that connect_meshtastic returns None and logs an error when repeated connection attempts with exponential backoff reach the maximum retries due to persistent MemoryError exceptions.
        """
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
        """
        Verifies that on_meshtastic_message handles various malformed packet inputs without raising exceptions.

        Tests the function's robustness against empty packets, missing or None fields, and invalid channel types.
        """
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
        """
        Verify that on_meshtastic_message logs an error when a plugin raises an exception during message processing.
        """
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
        """
        Verify that on_meshtastic_message logs an error when the Matrix relay integration fails during message processing.
        """
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
        """
        Test that on_meshtastic_message handles database errors gracefully during message processing.

        Simulates a failure in the database utility function when processing a Meshtastic message and verifies that no unhandled exceptions occur.
        """
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
        """
        Verifies that on_lost_meshtastic_connection logs an error when reconnection fails.
        """
        mock_interface = MagicMock()

        with patch("mmrelay.meshtastic_utils.connect_meshtastic", return_value=None):
            with patch("time.sleep"):  # Speed up test
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    with patch(
                        "mmrelay.meshtastic_utils.event_loop", None
                    ):  # Prevent async reconnect
                        on_lost_meshtastic_connection(mock_interface)
                        mock_logger.error.assert_called()

    def test_on_lost_meshtastic_connection_detection_source_edge_cases(self):
        """
        Test that on_lost_meshtastic_connection gracefully handles various invalid or unusual detection_source values without raising exceptions.
        """
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
        """
        Test the behavior of sendTextReply when no Meshtastic client is set.

        Verifies that sendTextReply returns None and logs an error if the Meshtastic client is unavailable.
        """
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None

        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
            result = sendTextReply(None, "test message", 12345)
            self.assertIsNone(result)
            mock_logger.error.assert_called()

    def test_sendTextReply_client_send_failure(self):
        """
        Test that sendTextReply returns None and logs an error when the client's send operation raises an exception.
        """
        mock_client = MagicMock()
        mock_client._sendPacket.side_effect = Exception("Send failed")

        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = mock_client

        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
            result = sendTextReply(mock_client, "test message", 12345)
            self.assertIsNone(result)
            mock_logger.error.assert_called()

    def test_is_running_as_service_detection_failure(self):
        """
        Test that is_running_as_service returns a boolean when process detection methods fail.

        Simulates failures in retrieving the parent process ID and process information to verify that is_running_as_service handles these errors gracefully without raising exceptions.
        """
        with patch("os.getppid", side_effect=OSError("Cannot get parent PID")):
            with patch(
                "psutil.Process", side_effect=Exception("Process info unavailable")
            ):
                # Should handle detection failures gracefully
                result = is_running_as_service()
                self.assertIsInstance(result, bool)

    def test_connect_meshtastic_concurrent_access(self):
        """
        Verify that connect_meshtastic returns None and handles concurrent connection attempts gracefully when a reconnection is already in progress.
        """
        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.reconnecting = True  # Simulate ongoing reconnection

        result = connect_meshtastic(config)
        # Should handle concurrent access gracefully
        self.assertIsNone(result)

    def test_connect_meshtastic_memory_constraint(self):
        """
        Test that connect_meshtastic handles MemoryError exceptions gracefully during serial connection attempts.

        Simulates a memory constraint scenario by forcing SerialInterface to raise MemoryError, and verifies that connect_meshtastic returns None and logs an error.
        """
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
        """
        Verifies that on_meshtastic_message can process a packet when the interface contains a very large node list without crashing.

        This test ensures robustness and scalability of message handling with extensive node data.
        """
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
        """
        Test that connect_meshtastic gracefully handles various invalid or incomplete configuration inputs.

        Verifies that the function returns None without raising exceptions when provided with None, empty, or malformed configuration dictionaries.
        """
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
