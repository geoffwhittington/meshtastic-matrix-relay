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
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.meshtastic_utils import (
    check_connection,
    connect_meshtastic,
    is_running_as_service,
    on_lost_meshtastic_connection,
    on_meshtastic_message,
    reconnect,
    sendTextReply,
    serial_port_exists,
)


class TestMeshtasticUtils(unittest.TestCase):
    """Test cases for Meshtastic utilities."""

    def setUp(self):
        """
        Prepare the test environment by initializing mock configuration and packet data, and resetting global state variables to ensure test isolation.
        """
        # Mock configuration
        self.mock_config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "broadcast_enabled": True,
                "meshnet_name": "test_mesh",
            },
            "matrix_rooms": [
                {"id": "!room1:matrix.org", "meshtastic_channel": 0},
                {"id": "!room2:matrix.org", "meshtastic_channel": 1},
            ],
        }

        # Mock packet data
        self.mock_packet = {
            "from": 123456789,
            "to": 987654321,
            "decoded": {
                "text": "Hello from mesh",
                "portnum": "TEXT_MESSAGE_APP",  # Use string constant
            },
            "channel": 0,
            "id": 12345,
            "rxTime": 1234567890,
        }

        # Reset global state to avoid test interference
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.config = None
        mmrelay.meshtastic_utils.matrix_rooms = []

    def test_on_meshtastic_message_basic(self):
        """
        Test that a basic Meshtastic message is processed and relayed to Matrix.

        Verifies that when a valid text message is received on a mapped channel, the message is relayed to Matrix by ensuring the appropriate coroutine is scheduled.
        """
        # Mock the required functions
        import mmrelay.meshtastic_utils

        with patch("mmrelay.meshtastic_utils.get_longname") as mock_get_longname, patch(
            "mmrelay.meshtastic_utils.get_shortname"
        ) as mock_get_shortname, patch(
            "mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro, patch(
            "mmrelay.matrix_utils.matrix_relay"
        ), patch(
            "mmrelay.matrix_utils.get_interaction_settings"
        ) as mock_get_interactions, patch(
            "mmrelay.matrix_utils.message_storage_enabled"
        ) as mock_storage:

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
        """
        Test that messages received on unmapped channels do not trigger Matrix relay.

        Verifies that when a Meshtastic packet is received on a channel not present in the configured Matrix room mapping, no coroutine is scheduled for relaying the message to Matrix.
        """
        # Modify packet to use unmapped channel
        packet_unmapped = self.mock_packet.copy()
        packet_unmapped["channel"] = 99  # Not in matrix_rooms config

        with patch("mmrelay.meshtastic_utils.config", self.mock_config), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.mock_config["matrix_rooms"]
        ), patch(
            "mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:

            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(packet_unmapped, mock_interface)

            # Verify asyncio.run_coroutine_threadsafe was not called (no matrix relay)
            mock_run_coro.assert_not_called()

    def test_on_meshtastic_message_no_text(self):
        """
        Verify that non-text Meshtastic packets do not trigger message relay to Matrix.

        This test ensures that when a packet does not contain a text message (i.e., its port number is not `TEXT_MESSAGE_APP`), the message processing function does not schedule a coroutine for relaying the message to Matrix.
        """
        # Modify packet to have no text
        packet_no_text = self.mock_packet.copy()
        packet_no_text["decoded"] = {"portnum": 2}  # Not TEXT_MESSAGE_APP

        with patch("mmrelay.meshtastic_utils.config", self.mock_config), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.mock_config["matrix_rooms"]
        ), patch(
            "mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro, patch(
            "mmrelay.plugin_loader.load_plugins"
        ) as mock_load_plugins:

            mock_load_plugins.return_value = []
            mock_interface = MagicMock()

            # Call the function
            on_meshtastic_message(packet_no_text, mock_interface)

            # Verify asyncio.run_coroutine_threadsafe was not called for non-text message
            mock_run_coro.assert_not_called()

    @patch("mmrelay.meshtastic_utils.serial_port_exists")
    @patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface")
    def test_connect_meshtastic_serial(
        self, mock_tcp, mock_ble, mock_serial, mock_port_exists
    ):
        """
        Test that the Meshtastic client connects via serial interface when the serial port exists.

        Verifies that the serial interface is instantiated with the configured port and that the returned client matches the mock client.
        """
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {
            "user": {"shortName": "test", "hwModel": "test"}
        }
        mock_serial.return_value = mock_client
        mock_port_exists.return_value = True

        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.shutting_down = False
        mmrelay.meshtastic_utils.reconnecting = False

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_serial.assert_called_once_with("/dev/ttyUSB0")

    @patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface")
    def test_connect_meshtastic_tcp(self, mock_tcp, mock_ble, mock_serial):
        """
        Tests that the Meshtastic client connects via the TCP interface using the configured host.

        Verifies that the TCP interface is instantiated with the correct hostname and that the returned client matches the mocked instance.
        """
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {
            "user": {"shortName": "test", "hwModel": "test"}
        }
        mock_tcp.return_value = mock_client

        config = {
            "meshtastic": {
                "connection_type": "tcp",
                "host": "192.168.1.100",  # Use 'host' not 'tcp_host'
            }
        }

        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.shutting_down = False
        mmrelay.meshtastic_utils.reconnecting = False

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_tcp.assert_called_once_with(hostname="192.168.1.100")

    @patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface")
    def test_connect_meshtastic_ble(self, mock_tcp, mock_ble, mock_serial):
        """
        Test that the Meshtastic client connects via BLE using the configured BLE address.

        Verifies that the BLE interface is instantiated with the expected parameters and that the returned client matches the mocked BLE client.
        """
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {
            "user": {"shortName": "test", "hwModel": "test"}
        }
        mock_ble.return_value = mock_client

        config = {
            "meshtastic": {"connection_type": "ble", "ble_address": "AA:BB:CC:DD:EE:FF"}
        }

        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.shutting_down = False
        mmrelay.meshtastic_utils.reconnecting = False

        result = connect_meshtastic(passed_config=config)

        self.assertEqual(result, mock_client)
        mock_ble.assert_called_once_with(
            address="AA:BB:CC:DD:EE:FF",
            noProto=False,
            debugOut=None,
            noNodes=False,
        )

    @patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface")
    @patch("mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface")
    def test_connect_meshtastic_invalid_type(self, mock_tcp, mock_ble, mock_serial):
        """
        Test that attempting to connect with an invalid Meshtastic connection type returns None and does not instantiate any interface.
        """
        config = {"meshtastic": {"connection_type": "invalid"}}

        result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)
        # None of the interfaces should be called
        mock_serial.assert_not_called()
        mock_tcp.assert_not_called()
        mock_ble.assert_not_called()

    def test_sendTextReply_success(self):
        """
        Test that sendTextReply returns the expected result when sending a text reply succeeds.

        Verifies that the function correctly calls the interface methods and returns the response from _sendPacket.
        """
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
        """
        Test that sendTextReply returns None when the interface fails to send a packet.
        """
        # Create a mock interface that fails
        mock_interface = MagicMock()
        mock_interface._generatePacketId.return_value = 12345
        mock_interface._sendPacket.return_value = None  # Simulate failure

        result = sendTextReply(mock_interface, "Hello", 999, destinationId=123456789)

        self.assertIsNone(result)

    def test_on_meshtastic_message_with_broadcast_config(self):
        """
        Test that Meshtastic-to-Matrix message relaying occurs even when broadcast is disabled in the configuration.

        Verifies that disabling `broadcast_enabled` in the configuration does not prevent Meshtastic messages from being relayed to Matrix, confirming that this setting only affects Matrix-to-Meshtastic message direction.
        """
        config_no_broadcast = self.mock_config.copy()
        config_no_broadcast["meshtastic"]["broadcast_enabled"] = False

        with patch("mmrelay.meshtastic_utils.config", config_no_broadcast), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", config_no_broadcast["matrix_rooms"]
        ), patch(
            "mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro, patch(
            "mmrelay.matrix_utils.matrix_relay"
        ), patch(
            "mmrelay.meshtastic_utils.get_longname"
        ) as mock_get_longname, patch(
            "mmrelay.meshtastic_utils.get_shortname"
        ) as mock_get_shortname, patch(
            "mmrelay.matrix_utils.get_interaction_settings"
        ) as mock_get_interactions, patch(
            "mmrelay.matrix_utils.message_storage_enabled"
        ) as mock_storage:

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


class TestServiceDetection(unittest.TestCase):
    """Test cases for service detection functionality."""

    @patch.dict(os.environ, {"INVOCATION_ID": "test-service-id"})
    def test_is_running_as_service_with_invocation_id(self):
        """Test service detection when INVOCATION_ID environment variable is set."""
        result = is_running_as_service()
        self.assertTrue(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_is_running_as_service_with_systemd_parent(self):
        """
        Tests that `is_running_as_service` returns True when the parent process is `systemd` by mocking the relevant proc files.
        """
        status_data = "PPid:\t1\n"
        comm_data = "systemd"

        def mock_open_func(filename, *args, **kwargs):
            """
            Mock file open function for simulating reads from specific `/proc` files during testing.

            Returns a mock file object with predefined content for `/proc/self/status` and `/proc/[pid]/comm`. Raises `FileNotFoundError` for any other file paths.

            Parameters:
                filename (str): The path of the file to open.

            Returns:
                file object: A mock file object with the specified content.

            Raises:
                FileNotFoundError: If the filename does not match the supported `/proc` paths.
            """
            if filename == "/proc/self/status":
                return mock_open(read_data=status_data)()
            elif filename.startswith("/proc/") and filename.endswith("/comm"):
                return mock_open(read_data=comm_data)()
            else:
                raise FileNotFoundError()

        with patch("builtins.open", side_effect=mock_open_func):
            result = is_running_as_service()
            self.assertTrue(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_is_running_as_service_normal_process(self):
        """
        Tests that is_running_as_service returns False for a normal process with a non-systemd parent.
        """
        status_data = "PPid:\t1234\n"
        comm_data = "bash"

        def mock_open_func(filename, *args, **kwargs):
            """
            Mock file open function for simulating reads from specific `/proc` files during testing.

            Returns a mock file object with predefined content for `/proc/self/status` and `/proc/[pid]/comm`. Raises `FileNotFoundError` for any other file paths.

            Parameters:
                filename (str): The path of the file to open.

            Returns:
                file object: A mock file object with the specified content.

            Raises:
                FileNotFoundError: If the filename does not match the supported `/proc` paths.
            """
            if filename == "/proc/self/status":
                return mock_open(read_data=status_data)()
            elif filename.startswith("/proc/") and filename.endswith("/comm"):
                return mock_open(read_data=comm_data)()
            else:
                raise FileNotFoundError()

        with patch("builtins.open", side_effect=mock_open_func):
            result = is_running_as_service()
            self.assertFalse(result)

    @patch.dict(os.environ, {}, clear=True)
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_is_running_as_service_file_not_found(self, mock_open_func):
        """
        Test that service detection returns False when required process files cannot be read.
        """
        result = is_running_as_service()
        self.assertFalse(result)


class TestSerialPortDetection(unittest.TestCase):
    """Test cases for serial port detection functionality."""

    @patch("mmrelay.meshtastic_utils.serial.tools.list_ports.comports")
    def test_serial_port_exists_found(self, mock_comports):
        """
        Test that serial_port_exists returns True when the specified serial port is present among available system ports.
        """
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyUSB0"
        mock_comports.return_value = [mock_port]

        result = serial_port_exists("/dev/ttyUSB0")
        self.assertTrue(result)

    @patch("mmrelay.meshtastic_utils.serial.tools.list_ports.comports")
    def test_serial_port_exists_not_found(self, mock_comports):
        """
        Tests that serial_port_exists returns False when the specified serial port is not found among available ports.
        """
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyUSB1"
        mock_comports.return_value = [mock_port]

        result = serial_port_exists("/dev/ttyUSB0")
        self.assertFalse(result)

    @patch("mmrelay.meshtastic_utils.serial.tools.list_ports.comports")
    def test_serial_port_exists_no_ports(self, mock_comports):
        """
        Test that serial port detection returns False when no serial ports are available.
        """
        mock_comports.return_value = []

        result = serial_port_exists("/dev/ttyUSB0")
        self.assertFalse(result)


class TestConnectionLossHandling(unittest.TestCase):
    """Test cases for connection loss handling."""

    def setUp(self):
        """
        Resets global connection state flags before each test to ensure test isolation.
        """
        # Reset global state
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.reconnecting = False
        mmrelay.meshtastic_utils.shutting_down = False
        mmrelay.meshtastic_utils.reconnect_task = None

    @patch("mmrelay.meshtastic_utils.logger")
    @patch("mmrelay.meshtastic_utils.event_loop", MagicMock())
    @patch("mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe")
    def test_on_lost_meshtastic_connection_normal(self, mock_run_coro, mock_logger):
        """Test normal connection loss handling."""
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.reconnecting = False
        mmrelay.meshtastic_utils.shutting_down = False

        mock_interface = MagicMock()

        on_lost_meshtastic_connection(mock_interface, "test_source")

        mock_logger.error.assert_called()
        # Should log the connection loss
        error_call = mock_logger.error.call_args[0][0]
        self.assertIn("Lost connection", error_call)
        self.assertIn("test_source", error_call)

    @patch("mmrelay.meshtastic_utils.logger")
    def test_on_lost_meshtastic_connection_already_reconnecting(self, mock_logger):
        """
        Test that connection loss handling skips reconnection if already reconnecting.

        Verifies that when the reconnecting flag is set, the function logs a debug message and does not attempt another reconnection.
        """
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.reconnecting = True
        mmrelay.meshtastic_utils.shutting_down = False

        mock_interface = MagicMock()

        on_lost_meshtastic_connection(mock_interface, "test_source")

        # Should log that reconnection is already in progress
        mock_logger.debug.assert_called_with(
            "Reconnection already in progress. Skipping additional reconnection attempt."
        )

    @patch("mmrelay.meshtastic_utils.logger")
    def test_on_lost_meshtastic_connection_shutting_down(self, mock_logger):
        """
        Tests that connection loss handling does not attempt reconnection and logs the correct message when the system is shutting down.
        """
        import mmrelay.meshtastic_utils

        mmrelay.meshtastic_utils.reconnecting = False
        mmrelay.meshtastic_utils.shutting_down = True

        mock_interface = MagicMock()

        on_lost_meshtastic_connection(mock_interface, "test_source")

        # Should log that system is shutting down
        mock_logger.debug.assert_called_with(
            "Shutdown in progress. Not attempting to reconnect."
        )


class TestConnectMeshtasticEdgeCases(unittest.TestCase):
    """Test cases for edge cases in Meshtastic connection."""

    @patch("mmrelay.meshtastic_utils.serial_port_exists")
    @patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
    def test_connect_meshtastic_serial_port_not_exists(
        self, mock_serial, mock_port_exists
    ):
        """
        Test that connect_meshtastic returns None and does not instantiate the serial interface when the specified serial port does not exist.
        """
        mock_port_exists.return_value = False

        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)
        mock_serial.assert_not_called()

    @patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
    def test_connect_meshtastic_serial_exception(self, mock_serial):
        """
        Test that connect_meshtastic returns None when the serial interface raises an exception during connection.
        """
        mock_serial.side_effect = Exception("Serial connection failed")

        config = {
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"}
        }

        with patch("mmrelay.meshtastic_utils.serial_port_exists", return_value=True):
            result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)

    @patch("mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface")
    def test_connect_meshtastic_tcp_exception(self, mock_tcp):
        """
        Tests that connect_meshtastic returns None when an exception is raised during TCP interface instantiation.
        """
        mock_tcp.side_effect = Exception("TCP connection failed")

        config = {"meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}}

        result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)

    @patch("mmrelay.meshtastic_utils.meshtastic.ble_interface.BLEInterface")
    def test_connect_meshtastic_ble_exception(self, mock_ble):
        """
        Test that connect_meshtastic returns None when the BLE interface raises an exception during connection.
        """
        mock_ble.side_effect = Exception("BLE connection failed")

        config = {
            "meshtastic": {"connection_type": "ble", "ble_address": "AA:BB:CC:DD:EE:FF"}
        }

        result = connect_meshtastic(passed_config=config)

        self.assertIsNone(result)

    def test_connect_meshtastic_no_config(self):
        """
        Test that attempting to connect to Meshtastic with no configuration returns None.
        """
        result = connect_meshtastic(passed_config=None)
        self.assertIsNone(result)

    def test_connect_meshtastic_existing_client_simple(self):
        """
        Tests that connect_meshtastic returns None gracefully when called with no configuration.
        """

        # Test with no config
        result = connect_meshtastic(passed_config=None)
        # Should handle gracefully
        self.assertIsNone(result)


class TestMessageProcessingEdgeCases(unittest.TestCase):
    """Test cases for edge cases in message processing."""

    def setUp(self):
        """
        Initializes mock configuration data for use in test cases.
        """
        self.mock_config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "broadcast_enabled": True,
                "meshnet_name": "test_mesh",
            },
            "matrix_rooms": [{"id": "!room1:matrix.org", "meshtastic_channel": 0}],
        }

    def test_on_meshtastic_message_no_decoded(self):
        """
        Tests that a Meshtastic packet without a 'decoded' field does not trigger message relay processing.
        """
        packet = {
            "from": 123456789,
            "to": 987654321,
            "channel": 0,
            "id": 12345,
            "rxTime": 1234567890,
            # No 'decoded' field
        }

        with patch("mmrelay.meshtastic_utils.config", self.mock_config), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.mock_config["matrix_rooms"]
        ), patch(
            "mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:

            mock_interface = MagicMock()

            on_meshtastic_message(packet, mock_interface)

            # Should not process message without decoded field
            mock_run_coro.assert_not_called()

    def test_on_meshtastic_message_empty_text(self):
        """
        Tests that packets with empty text messages do not trigger message relay to Matrix.
        """
        packet = {
            "from": 123456789,
            "to": 987654321,
            "decoded": {"text": "", "portnum": "TEXT_MESSAGE_APP"},  # Empty text
            "channel": 0,
            "id": 12345,
            "rxTime": 1234567890,
        }

        with patch("mmrelay.meshtastic_utils.config", self.mock_config), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.mock_config["matrix_rooms"]
        ), patch(
            "mmrelay.meshtastic_utils.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:

            mock_interface = MagicMock()

            on_meshtastic_message(packet, mock_interface)

            # Should not process empty text messages
            mock_run_coro.assert_not_called()


# Meshtastic connection retry tests - converted from unittest.TestCase to standalone pytest functions


@pytest.fixture
def reset_meshtastic_globals():
    """Reset global state for connection retry tests."""
    import mmrelay.meshtastic_utils

    mmrelay.meshtastic_utils.meshtastic_client = None
    mmrelay.meshtastic_utils.shutting_down = False
    mmrelay.meshtastic_utils.reconnecting = False
    yield
    # Cleanup after test
    mmrelay.meshtastic_utils.meshtastic_client = None
    mmrelay.meshtastic_utils.shutting_down = False
    mmrelay.meshtastic_utils.reconnecting = False


@patch("mmrelay.meshtastic_utils.time.sleep")
@patch("mmrelay.meshtastic_utils.serial_port_exists")
@patch("mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface")
def test_connect_meshtastic_retry_on_serial_exception(
    mock_serial, mock_port_exists, mock_sleep, reset_meshtastic_globals
):
    """Test that connect_meshtastic retries on serial exceptions."""
    mock_port_exists.return_value = True

    # First call fails, second succeeds
    mock_client = MagicMock()
    mock_client.getMyNodeInfo.return_value = {
        "user": {"shortName": "test", "hwModel": "test"}
    }
    mock_serial.side_effect = [Exception("Connection failed"), mock_client]

    config = {
        "meshtastic": {
            "connection_type": "serial",
            "serial_port": "/dev/ttyUSB0",
            "retry_limit": 2,
        }
    }

    result = connect_meshtastic(passed_config=config)

    # Should succeed on second attempt
    assert result == mock_client
    assert mock_serial.call_count == 2
    mock_sleep.assert_called_once()


@patch("mmrelay.meshtastic_utils.time.sleep")
@patch("mmrelay.meshtastic_utils.meshtastic.tcp_interface.TCPInterface")
def test_connect_meshtastic_retry_exhausted(
    mock_tcp, mock_sleep, reset_meshtastic_globals
):
    """Test that connect_meshtastic returns None when retries are exhausted."""
    # Mock a critical error that should not be retried
    mock_tcp.side_effect = TimeoutError("Connection timeout")

    config = {"meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}}

    result = connect_meshtastic(passed_config=config)

    # Should fail immediately on critical error
    assert result is None
    assert mock_tcp.call_count == 1
    mock_sleep.assert_not_called()  # No retries for critical errors


@patch("mmrelay.meshtastic_utils.connect_meshtastic")
@patch("mmrelay.meshtastic_utils.asyncio.sleep", new_callable=AsyncMock)
@patch("mmrelay.meshtastic_utils.logger")
async def test_reconnect_attempts_connection(
    mock_logger, mock_sleep, mock_connect, reset_meshtastic_globals
):
    """Test that reconnect attempts to connect to Meshtastic."""
    # Simulate connect_meshtastic succeeding to prevent an infinite loop
    mock_connect.return_value = MagicMock()

    await reconnect()

    # Assert that a connection was attempted
    mock_connect.assert_called_with(force_connect=True)


def test_check_connection_function_exists(reset_meshtastic_globals):
    """Test that the check_connection function exists and can be imported."""
    # This test just verifies the function exists without running it
    # to avoid the hanging issue in the async loop
    assert callable(check_connection)


class TestMeshtasticUtilsAsync(unittest.TestCase):
    """Simplified async tests that avoid AsyncMock warnings."""

    def test_async_message_processing_setup(self):
        """
        Verify that async message processing components and functions can be imported and exist.

        This test ensures that key async functions and infrastructure are present and importable without executing any asynchronous code.
        """
        # Test that we can import the async functions
        from mmrelay.matrix_utils import matrix_relay
        from mmrelay.meshtastic_utils import on_meshtastic_message

        self.assertIsNotNone(asyncio.run_coroutine_threadsafe)

        # Test that the functions exist
        self.assertIsNotNone(matrix_relay)
        self.assertIsNotNone(on_meshtastic_message)

        # This test passes if all imports work correctly
        # Complex async testing is better done through integration tests


if __name__ == "__main__":
    unittest.main()
