#!/usr/bin/env python3
"""
Test suite for Integration scenarios and end-to-end testing in MMRelay.

Tests integration scenarios including:
- Complete message flow from Meshtastic to Matrix
- Complete message flow from Matrix to Meshtastic
- Plugin interaction chains
- Configuration loading and validation
- Service lifecycle management
- Error recovery scenarios
- Multi-room message routing
"""

import asyncio
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.config import load_config
from mmrelay.db_utils import initialize_database
from mmrelay.matrix_utils import connect_matrix
from mmrelay.meshtastic_utils import connect_meshtastic, on_meshtastic_message


class TestIntegrationScenarios(unittest.TestCase):
    """Test cases for integration scenarios and end-to-end flows."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset global state
        self._reset_global_state()

    def tearDown(self):
        """Clean up after each test method."""
        self._reset_global_state()

    def _reset_global_state(self):
        """Reset global state across all modules."""
        # Reset meshtastic_utils globals
        if "mmrelay.meshtastic_utils" in sys.modules:
            module = sys.modules["mmrelay.meshtastic_utils"]
            module.config = None
            module.matrix_rooms = []
            module.meshtastic_client = None
            module.event_loop = None
            module.reconnecting = False
            module.shutting_down = False
            module.reconnect_task = None
            module.subscribed_to_messages = False
            module.subscribed_to_connection_lost = False

        # Reset matrix_utils globals
        if "mmrelay.matrix_utils" in sys.modules:
            module = sys.modules["mmrelay.matrix_utils"]
            if hasattr(module, "config"):
                module.config = None
            if hasattr(module, "matrix_client"):
                module.matrix_client = None

        # Reset plugin_loader globals
        if "mmrelay.plugin_loader" in sys.modules:
            module = sys.modules["mmrelay.plugin_loader"]
            if hasattr(module, "config"):
                module.config = None
            if hasattr(module, "sorted_active_plugins"):
                module.sorted_active_plugins = []
            if hasattr(module, "plugins_loaded"):
                module.plugins_loaded = False

        # Reset config globals
        if "mmrelay.config" in sys.modules:
            module = sys.modules["mmrelay.config"]
            if hasattr(module, "config"):
                module.config = None

        # Reset db_utils globals
        if "mmrelay.db_utils" in sys.modules:
            module = sys.modules["mmrelay.db_utils"]
            if hasattr(module, "config"):
                module.config = None

    def test_complete_meshtastic_to_matrix_flow(self):
        """Test complete message flow from Meshtastic to Matrix."""
        # Create test configuration
        config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@test:matrix.org",
            },
            "matrix_rooms": [{"id": "!room1:matrix.org", "meshtastic_channel": 0}],
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"},
            "plugins": {"debug": {"active": True}},
        }

        # Mock Meshtastic packet
        packet = {
            "decoded": {"text": "Hello from Meshtastic!", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
            "to": 4294967295,  # BROADCAST_NUM
            "id": 123456789,
        }

        mock_meshtastic_interface = MagicMock()
        mock_meshtastic_interface.nodes = {
            "!12345678": {
                "user": {"id": "!12345678", "longName": "Test Node", "shortName": "TN"}
            }
        }

        with patch("mmrelay.matrix_utils.matrix_relay") as mock_matrix_relay:
            with patch("mmrelay.plugin_loader.load_plugins") as mock_load_plugins:
                # Mock debug plugin
                mock_plugin = MagicMock()
                mock_plugin.handle_meshtastic_message = AsyncMock(return_value=False)
                mock_load_plugins.return_value = [mock_plugin]

                # Set up global state
                import mmrelay.meshtastic_utils

                mmrelay.meshtastic_utils.config = config
                mmrelay.meshtastic_utils.matrix_rooms = config["matrix_rooms"]

                # Process the message
                on_meshtastic_message(packet, mock_meshtastic_interface)

                # Verify Matrix relay was called
                mock_matrix_relay.assert_called_once()

                # Verify plugin was called
                mock_plugin.handle_meshtastic_message.assert_called_once()

    def test_complete_matrix_to_meshtastic_flow(self):
        """Test complete message flow from Matrix to Meshtastic."""

        async def async_test():
            # Create test configuration
            config = {
                "matrix": {
                    "homeserver": "https://matrix.org",
                    "access_token": "test_token",
                    "bot_user_id": "@test:matrix.org",
                },
                "matrix_rooms": [{"id": "!room1:matrix.org", "meshtastic_channel": 0}],
                "meshtastic": {
                    "connection_type": "serial",
                    "serial_port": "/dev/ttyUSB0",
                },
                "plugins": {"help": {"active": True}},
            }

            # Mock Matrix event
            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"

            mock_event = MagicMock()
            mock_event.sender = "@user:matrix.org"
            mock_event.body = "!help"

            # Mock Meshtastic client
            mock_meshtastic_client = MagicMock()

            with patch("mmrelay.plugin_loader.load_plugins") as mock_load_plugins:
                # Mock help plugin that intercepts the message
                mock_plugin = MagicMock()
                mock_plugin.handle_room_message = AsyncMock(
                    return_value=True
                )  # Intercepts
                mock_load_plugins.return_value = [mock_plugin]

                # Set up global state
                import mmrelay.matrix_utils

                mmrelay.matrix_utils.config = config
                mmrelay.matrix_utils.matrix_rooms = config["matrix_rooms"]

                import mmrelay.meshtastic_utils

                mmrelay.meshtastic_utils.meshtastic_client = mock_meshtastic_client

                # Import and call the Matrix message handler
                from mmrelay.matrix_utils import on_room_message

                await on_room_message(mock_room, mock_event)

                # Verify plugin was called and intercepted the message
                mock_plugin.handle_room_message.assert_called_once()

        asyncio.run(async_test())

    def test_plugin_chain_processing(self):
        """Test multiple plugins processing the same message in priority order."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        mock_interface = MagicMock()

        # Create plugins with different priorities
        mock_plugin1 = MagicMock()
        mock_plugin1.priority = 1
        mock_plugin1.handle_meshtastic_message = AsyncMock(return_value=False)

        mock_plugin2 = MagicMock()
        mock_plugin2.priority = 5
        mock_plugin2.handle_meshtastic_message = AsyncMock(return_value=False)

        mock_plugin3 = MagicMock()
        mock_plugin3.priority = 10
        mock_plugin3.handle_meshtastic_message = AsyncMock(
            return_value=True
        )  # Intercepts

        with patch("mmrelay.plugin_loader.load_plugins") as mock_load_plugins:
            # Return plugins in random order (should be sorted by priority)
            mock_load_plugins.return_value = [mock_plugin2, mock_plugin1, mock_plugin3]

            on_meshtastic_message(packet, mock_interface)

            # Verify all plugins were called in priority order
            mock_plugin1.handle_meshtastic_message.assert_called_once()
            mock_plugin2.handle_meshtastic_message.assert_called_once()
            mock_plugin3.handle_meshtastic_message.assert_called_once()

    def test_configuration_loading_and_validation_flow(self):
        """Test complete configuration loading and validation flow."""
        # Create temporary config file
        config_data = """
matrix:
  homeserver: https://matrix.org
  access_token: test_token
  bot_user_id: '@test:matrix.org'

matrix_rooms:
  - id: '!room1:matrix.org'
    meshtastic_channel: 0

meshtastic:
  connection_type: serial
  serial_port: /dev/ttyUSB0

plugins:
  debug:
    active: true
  help:
    active: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_data)
            temp_config_path = f.name

        try:
            # Load configuration
            config = load_config(config_file=temp_config_path)

            # Verify configuration structure
            self.assertIsNotNone(config)
            self.assertIn("matrix", config)
            self.assertIn("matrix_rooms", config)
            self.assertIn("meshtastic", config)
            self.assertIn("plugins", config)

            # Test configuration validation
            from mmrelay.cli import check_config

            with patch("mmrelay.cli.get_config_paths", return_value=[temp_config_path]):
                result = check_config()
                self.assertTrue(result)

        finally:
            os.unlink(temp_config_path)

    def test_database_initialization_and_usage_flow(self):
        """Test database initialization and basic usage flow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.sqlite")

            with patch("mmrelay.db_utils.get_db_path", return_value=db_path):
                # Initialize database
                initialize_database()

                # Test database operations
                from mmrelay.db_utils import (
                    get_longname,
                    get_message_map_by_meshtastic_id,
                    get_shortname,
                    save_longname,
                    save_shortname,
                    store_message_map,
                )

                # Test name storage and retrieval
                save_longname("!12345678", "Test Node")
                save_shortname("!12345678", "TN")

                self.assertEqual(get_longname("!12345678"), "Test Node")
                self.assertEqual(get_shortname("!12345678"), "TN")

                # Test message mapping
                store_message_map(
                    "mesh123", "matrix456", "!room:matrix.org", "test message"
                )
                mapping = get_message_map_by_meshtastic_id("mesh123")
                self.assertIsNotNone(mapping)

    def test_error_recovery_scenario(self):
        """Test error recovery in various failure scenarios."""
        config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@test:matrix.org",
            },
            "matrix_rooms": [{"id": "!room1:matrix.org", "meshtastic_channel": 0}],
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"},
        }

        # Test Matrix connection failure recovery
        with patch("mmrelay.matrix_utils.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login.side_effect = Exception("Login failed")
            mock_client_class.return_value = mock_client

            async def test_matrix_recovery():
                result = await connect_matrix(config)
                self.assertIsNone(result)  # Should handle failure gracefully

            asyncio.run(test_matrix_recovery())

        # Test Meshtastic connection failure recovery
        with patch("mmrelay.meshtastic_utils.serial_port_exists", return_value=True):
            with patch(
                "meshtastic.serial_interface.SerialInterface",
                side_effect=Exception("Connection failed"),
            ):
                with patch("time.sleep"):  # Speed up test
                    result = connect_meshtastic(config)
                    self.assertIsNone(result)  # Should handle failure gracefully

    def test_multi_room_message_routing(self):
        """Test message routing to multiple Matrix rooms."""
        config = {
            "matrix_rooms": [
                {"id": "!room1:matrix.org", "meshtastic_channel": 0},
                {"id": "!room2:matrix.org", "meshtastic_channel": 0},
                {
                    "id": "!room3:matrix.org",
                    "meshtastic_channel": 1,
                },  # Different channel
            ]
        }

        packet = {
            "decoded": {"text": "Multi-room test", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,  # Should route to room1 and room2, not room3
            "to": 4294967295,
            "id": 123456789,
        }

        mock_interface = MagicMock()

        with patch("mmrelay.matrix_utils.matrix_relay") as mock_matrix_relay:
            with patch("mmrelay.plugin_loader.load_plugins", return_value=[]):
                # Set up global state
                import mmrelay.meshtastic_utils

                mmrelay.meshtastic_utils.config = config
                mmrelay.meshtastic_utils.matrix_rooms = config["matrix_rooms"]

                on_meshtastic_message(packet, mock_interface)

                # Should be called for each matching room
                self.assertEqual(mock_matrix_relay.call_count, 2)

    def test_service_lifecycle_simulation(self):
        """Test service lifecycle management simulation."""
        # Test service detection
        from mmrelay.meshtastic_utils import is_running_as_service

        # Mock systemd environment
        with patch("os.getppid", return_value=1):
            with patch("psutil.Process") as mock_process:
                mock_parent = MagicMock()
                mock_parent.name.return_value = "systemd"
                mock_process.return_value.parent.return_value = mock_parent

                result = is_running_as_service()
                self.assertTrue(result)

        # Test service installation
        from mmrelay.setup_utils import install_service

        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=True):
                with patch(
                    "mmrelay.setup_utils.reload_daemon", return_value=True
                ):
                    with patch(
                        "mmrelay.setup_utils.check_loginctl_available",
                        return_value=False,
                    ):
                        result = install_service()
                        self.assertTrue(result)

    def test_concurrent_message_processing(self):
        """Test concurrent message processing scenarios."""
        packets = []
        for i in range(10):
            packets.append(
                {
                    "decoded": {"text": f"Message {i}", "portnum": 1},
                    "fromId": f"!{i:08x}",
                    "channel": 0,
                    "id": i,
                }
            )

        mock_interface = MagicMock()

        with patch("mmrelay.plugin_loader.load_plugins", return_value=[]):
            with patch("mmrelay.matrix_utils.matrix_relay") as mock_matrix_relay:
                # Set up minimal config
                import mmrelay.meshtastic_utils

                mmrelay.meshtastic_utils.config = {"matrix_rooms": []}
                mmrelay.meshtastic_utils.matrix_rooms = []

                # Process multiple messages
                for packet in packets:
                    on_meshtastic_message(packet, mock_interface)

                # All messages should be processed without interference
                # (Matrix relay not called since no rooms configured)
                mock_matrix_relay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
