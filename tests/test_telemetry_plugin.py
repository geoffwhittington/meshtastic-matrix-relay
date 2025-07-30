#!/usr/bin/env python3
"""
Test suite for the MMRelay telemetry plugin.

Tests the telemetry data collection and graphing functionality including:
- Telemetry data processing and storage
- Time period generation
- Matrix command handling
- Graph generation and image upload
- Device metrics parsing
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.telemetry_plugin import Plugin


class TestTelemetryPlugin(unittest.TestCase):
    """Test cases for the telemetry plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        
        # Mock database operations
        self.plugin.get_node_data = MagicMock(return_value=[])
        self.plugin.set_node_data = MagicMock()
        self.plugin.get_data = MagicMock(return_value=[])
        
        # Mock Matrix client methods
        self.plugin.send_matrix_message = AsyncMock()

    def test_plugin_name(self):
        """Test that plugin name is correctly set."""
        self.assertEqual(self.plugin.plugin_name, "telemetry")

    def test_max_data_rows_per_node(self):
        """Test that max data rows per node is set correctly."""
        self.assertEqual(self.plugin.max_data_rows_per_node, 50)

    def test_commands(self):
        """Test that commands returns expected list."""
        commands = self.plugin.commands()
        expected = ["batteryLevel", "voltage", "airUtilTx"]
        self.assertEqual(commands, expected)

    def test_description(self):
        """Test that description returns expected string."""
        description = self.plugin.description()
        self.assertEqual(description, "Graph of avg Mesh telemetry value for last 12 hours")

    def test_get_matrix_commands(self):
        """Test that get_matrix_commands returns expected list."""
        commands = self.plugin.get_matrix_commands()
        expected = ["batteryLevel", "voltage", "airUtilTx"]
        self.assertEqual(commands, expected)

    def test_get_mesh_commands(self):
        """Test that get_mesh_commands returns empty list."""
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, [])

    def test_generate_timeperiods_default(self):
        """Test time period generation with default 12 hours."""
        with patch('mmrelay.plugins.telemetry_plugin.datetime') as mock_datetime:
            # Mock current time
            mock_now = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            intervals = self.plugin._generate_timeperiods()
            
            # Should have 13 intervals (12 hours + 1 for end time)
            self.assertEqual(len(intervals), 13)
            
            # First interval should be 12 hours ago
            expected_start = mock_now - timedelta(hours=12)
            self.assertEqual(intervals[0], expected_start)
            
            # Last interval should be current time
            self.assertEqual(intervals[-1], mock_now)
            
            # Each interval should be 1 hour apart
            for i in range(len(intervals) - 1):
                diff = intervals[i + 1] - intervals[i]
                self.assertEqual(diff, timedelta(hours=1))

    def test_generate_timeperiods_custom_hours(self):
        """Test time period generation with custom hours."""
        with patch('mmrelay.plugins.telemetry_plugin.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            intervals = self.plugin._generate_timeperiods(hours=6)
            
            # Should have 7 intervals (6 hours + 1 for end time)
            self.assertEqual(len(intervals), 7)
            
            # First interval should be 6 hours ago
            expected_start = mock_now - timedelta(hours=6)
            self.assertEqual(intervals[0], expected_start)

    def test_handle_meshtastic_message_valid_telemetry(self):
        """Test handling valid telemetry message."""
        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TELEMETRY_APP",
                "telemetry": {
                    "time": 1642248000,  # Unix timestamp
                    "deviceMetrics": {
                        "batteryLevel": 85,
                        "voltage": 4.2,
                        "airUtilTx": 12.5
                    }
                }
            }
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            
            # Should return False (doesn't relay to Matrix)
            self.assertFalse(result)
            
            # Should store telemetry data
            self.plugin.set_node_data.assert_called_once()
            call_args = self.plugin.set_node_data.call_args
            self.assertEqual(call_args.kwargs['meshtastic_id'], "!12345678")
            
            # Check stored data structure
            stored_data = call_args.kwargs['node_data']
            self.assertEqual(len(stored_data), 1)
            self.assertEqual(stored_data[0]['time'], 1642248000)
            self.assertEqual(stored_data[0]['batteryLevel'], 85)
            self.assertEqual(stored_data[0]['voltage'], 4.2)
            self.assertEqual(stored_data[0]['airUtilTx'], 12.5)
        
        import asyncio
        asyncio.run(run_test())

    def test_handle_meshtastic_message_partial_metrics(self):
        """Test handling telemetry message with partial device metrics."""
        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TELEMETRY_APP",
                "telemetry": {
                    "time": 1642248000,
                    "deviceMetrics": {
                        "batteryLevel": 75
                        # Missing voltage and airUtilTx
                    }
                }
            }
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            
            self.assertFalse(result)
            
            # Check stored data has default values for missing metrics
            call_args = self.plugin.set_node_data.call_args
            stored_data = call_args.kwargs['node_data']
            self.assertEqual(stored_data[0]['batteryLevel'], 75)
            self.assertEqual(stored_data[0]['voltage'], 0)  # Default value
            self.assertEqual(stored_data[0]['airUtilTx'], 0)  # Default value
        
        import asyncio
        asyncio.run(run_test())

    def test_handle_meshtastic_message_non_telemetry(self):
        """Test handling non-telemetry message."""
        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Hello world"
            }
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            
            # Should return None (not processed)
            self.assertIsNone(result)
            
            # Should not store any data
            self.plugin.set_node_data.assert_not_called()
        
        import asyncio
        asyncio.run(run_test())

    def test_handle_meshtastic_message_missing_device_metrics(self):
        """Test handling telemetry message without device metrics."""
        packet = {
            "fromId": "!12345678",
            "decoded": {
                "portnum": "TELEMETRY_APP",
                "telemetry": {
                    "time": 1642248000
                    # Missing deviceMetrics
                }
            }
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            
            # Should return None (not processed)
            self.assertIsNone(result)
            
            # Should not store any data
            self.plugin.set_node_data.assert_not_called()
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.matrix_utils.bot_command')
    def test_matches_with_valid_command(self, mock_bot_command):
        """Test matches method with valid telemetry command."""
        mock_bot_command.side_effect = lambda cmd, event: cmd == "batteryLevel"

        event = MagicMock()
        result = self.plugin.matches(event)

        self.assertTrue(result)
        # Should check all commands until it finds a match
        self.assertTrue(mock_bot_command.called)

    @patch('mmrelay.matrix_utils.bot_command')
    def test_matches_with_no_command(self, mock_bot_command):
        """Test matches method with no matching command."""
        mock_bot_command.return_value = False

        event = MagicMock()
        result = self.plugin.matches(event)

        self.assertFalse(result)
        # Should check all commands
        self.assertEqual(mock_bot_command.call_count, 3)

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

    def test_handle_room_message_invalid_regex(self):
        """Test handle_room_message with invalid command format."""
        self.plugin.matches = MagicMock(return_value=True)

        room = MagicMock()
        event = MagicMock()
        full_message = "some invalid message format"

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, full_message)
            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.matrix_utils.connect_matrix')
    @patch('mmrelay.matrix_utils.upload_image')
    @patch('mmrelay.matrix_utils.send_room_image')
    @patch('mmrelay.plugins.telemetry_plugin.plt.xticks')
    @patch('mmrelay.plugins.telemetry_plugin.plt.subplots')
    def test_handle_room_message_valid_command_no_node(self, mock_subplots, mock_xticks, mock_send_image, mock_upload, mock_connect):
        """Test handle_room_message with valid command but no specific node."""
        self.plugin.matches = MagicMock(return_value=True)

        # Mock matplotlib
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        # Mock canvas and image operations
        mock_canvas = MagicMock()
        mock_fig.canvas = mock_canvas

        # Mock PIL Image operations
        with patch('mmrelay.plugins.telemetry_plugin.Image') as mock_image_class:
            mock_image = MagicMock()
            mock_image.size = (800, 600)
            mock_image.tobytes.return_value = b'fake_image_data'
            mock_image_class.open.return_value = mock_image
            mock_image_class.frombytes.return_value = mock_image

            # Mock Matrix operations
            mock_matrix_client = AsyncMock()
            mock_connect.return_value = mock_matrix_client
            mock_upload.return_value = {"content_uri": "mxc://example.com/image"}

            room = MagicMock()
            room.room_id = "!test:matrix.org"
            event = MagicMock()
            full_message = "bot: !batteryLevel"

            async def run_test():
                result = await self.plugin.handle_room_message(room, event, full_message)

                self.assertTrue(result)

                # Should create plot
                mock_subplots.assert_called_once()
                mock_ax.plot.assert_called_once()
                mock_ax.set_title.assert_called_once()
                mock_ax.set_xlabel.assert_called_once_with("Hour")
                mock_ax.set_ylabel.assert_called_once_with("batteryLevel")

                # Should upload and send image
                mock_upload.assert_called_once()
                mock_send_image.assert_called_once()

            import asyncio
            asyncio.run(run_test())

    @patch('mmrelay.matrix_utils.connect_matrix')
    @patch('mmrelay.matrix_utils.upload_image')
    @patch('mmrelay.matrix_utils.send_room_image')
    @patch('mmrelay.plugins.telemetry_plugin.plt.xticks')
    @patch('mmrelay.plugins.telemetry_plugin.plt.subplots')
    def test_handle_room_message_with_specific_node(self, mock_subplots, mock_xticks, mock_send_image, mock_upload, mock_connect):
        """Test handle_room_message with specific node parameter."""
        self.plugin.matches = MagicMock(return_value=True)

        # Mock node data
        mock_node_data = [
            {"time": 1642248000, "voltage": 4.2},
            {"time": 1642251600, "voltage": 4.1}
        ]
        self.plugin.get_node_data.return_value = mock_node_data

        # Mock matplotlib
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)
        mock_canvas = MagicMock()
        mock_fig.canvas = mock_canvas

        # Mock PIL Image operations
        with patch('mmrelay.plugins.telemetry_plugin.Image') as mock_image_class:
            mock_image = MagicMock()
            mock_image.size = (800, 600)
            mock_image.tobytes.return_value = b'fake_image_data'
            mock_image_class.open.return_value = mock_image
            mock_image_class.frombytes.return_value = mock_image

            # Mock Matrix operations
            mock_matrix_client = AsyncMock()
            mock_connect.return_value = mock_matrix_client
            mock_upload.return_value = {"content_uri": "mxc://example.com/image"}

            room = MagicMock()
            room.room_id = "!test:matrix.org"
            event = MagicMock()
            full_message = "bot: !voltage NodeABC"

            async def run_test():
                result = await self.plugin.handle_room_message(room, event, full_message)

                self.assertTrue(result)

                # Should get data for specific node
                self.plugin.get_node_data.assert_called_with("NodeABC")

                # Should set title with node name
                title_call = mock_ax.set_title.call_args[0][0]
                self.assertIn("NodeABC", title_call)
                self.assertIn("voltage", title_call)

            import asyncio
            asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
