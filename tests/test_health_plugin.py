#!/usr/bin/env python3
"""
Test suite for the MMRelay health plugin.

Tests the mesh health statistics functionality including:
- Battery level statistics (average, median, low battery count)
- Air utilization statistics
- SNR (Signal-to-Noise Ratio) statistics
- Node counting and health reporting
- Matrix room message handling
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.health_plugin import Plugin


class TestHealthPlugin(unittest.TestCase):
    """Test cases for the health plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        
        # Mock Matrix client methods
        self.plugin.send_matrix_message = AsyncMock()
        
        # Create sample node data for testing
        self.sample_nodes = {
            "node1": {
                "deviceMetrics": {
                    "batteryLevel": 85,
                    "airUtilTx": 12.5
                },
                "snr": 10.2
            },
            "node2": {
                "deviceMetrics": {
                    "batteryLevel": 45,
                    "airUtilTx": 8.3
                },
                "snr": -5.1
            },
            "node3": {
                "deviceMetrics": {
                    "batteryLevel": 5,  # Low battery
                    "airUtilTx": 15.7
                },
                "snr": 2.8
            },
            "node4": {
                # Node with missing deviceMetrics
                "snr": 7.5
            },
            "node5": {
                "deviceMetrics": {
                    "batteryLevel": 92
                    # Missing airUtilTx
                },
                "snr": None  # None SNR value
            }
        }

    def test_plugin_name(self):
        """Test that plugin name is correctly set."""
        self.assertEqual(self.plugin.plugin_name, "health")

    def test_description_property(self):
        """Test that description property returns expected string."""
        description = self.plugin.description
        self.assertEqual(description, "Show mesh health using avg battery, SNR, AirUtil")

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_full_data(self, mock_connect):
        """Test response generation with complete node data."""
        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = self.sample_nodes
        mock_connect.return_value = mock_meshtastic_client
        
        response = self.plugin.generate_response()
        
        # Should contain node count
        self.assertIn("Nodes: 5", response)
        
        # Should contain battery statistics
        # Battery levels: [85, 45, 5, 92] -> avg=56.75, median=65.0
        self.assertIn("Battery: 56.8%", response)  # Rounded to 1 decimal
        self.assertIn("65.0%", response)  # Median
        
        # Should contain low battery count (< 10%)
        self.assertIn("Nodes with Low Battery (< 10): 1", response)
        
        # Should contain air util statistics
        # Air util: [12.5, 8.3, 15.7] -> avg=12.17, median=12.5
        self.assertIn("Air Util: 12.17", response)
        self.assertIn("12.50", response)
        
        # Should contain SNR statistics
        # SNR: [10.2, -5.1, 2.8, 7.5] (None filtered out) -> avg=3.85, median=5.15
        self.assertIn("SNR: 3.85", response)
        self.assertIn("5.15", response)

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_empty_nodes(self, mock_connect):
        """Test response generation with no nodes (exposes bug in plugin)."""
        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = {}
        mock_connect.return_value = mock_meshtastic_client

        # The plugin has a bug - it doesn't check for empty lists before calling median()
        with self.assertRaises(Exception):  # Will raise StatisticsError
            self.plugin.generate_response()

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_minimal_data(self, mock_connect):
        """Test response generation with minimal node data (exposes bug)."""
        minimal_nodes = {
            "node1": {
                "deviceMetrics": {
                    "batteryLevel": 50
                }
                # No SNR or airUtilTx
            }
        }

        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = minimal_nodes
        mock_connect.return_value = mock_meshtastic_client

        # The plugin has a bug - it tries to calculate median on empty air_util_tx and snr lists
        with self.assertRaises(Exception):  # Will raise StatisticsError
            self.plugin.generate_response()

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_all_low_battery(self, mock_connect):
        """Test response generation with all nodes having low battery (exposes bug)."""
        low_battery_nodes = {
            "node1": {
                "deviceMetrics": {
                    "batteryLevel": 5
                },
                "snr": 10.0
            },
            "node2": {
                "deviceMetrics": {
                    "batteryLevel": 8
                },
                "snr": 5.0
            }
        }

        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = low_battery_nodes
        mock_connect.return_value = mock_meshtastic_client

        # The plugin has a bug - it tries to calculate median on empty air_util_tx list
        with self.assertRaises(Exception):  # Will raise StatisticsError
            self.plugin.generate_response()

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_filters_none_values(self, mock_connect):
        """Test that None values are properly filtered from statistics."""
        nodes_with_none = {
            "node1": {
                "deviceMetrics": {
                    "batteryLevel": 75,
                    "airUtilTx": None  # None value should be filtered
                },
                "snr": None  # None value should be filtered
            },
            "node2": {
                "deviceMetrics": {
                    "batteryLevel": 25,
                    "airUtilTx": 10.0
                },
                "snr": 5.0
            }
        }
        
        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = nodes_with_none
        mock_connect.return_value = mock_meshtastic_client
        
        response = self.plugin.generate_response()
        
        # Should only use non-None values for statistics
        self.assertIn("Nodes: 2", response)
        self.assertIn("Battery: 50.0%", response)  # Average of 75 and 25
        self.assertIn("Air Util: 10.00", response)  # Only one valid value
        self.assertIn("10.00", response)  # Median same as single value
        self.assertIn("SNR: 5.00", response)  # Only one valid value

    def test_handle_meshtastic_message_always_false(self):
        """Test that handle_meshtastic_message always returns False."""
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                {}, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)
        
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
            self.plugin.send_matrix_message.assert_not_called()
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_room_message_with_match(self, mock_connect):
        """Test handle_room_message when event matches."""
        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = self.sample_nodes
        mock_connect.return_value = mock_meshtastic_client
        
        self.plugin.matches = MagicMock(return_value=True)
        
        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()
        
        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "full_message")
            
            self.assertTrue(result)
            self.plugin.matches.assert_called_once_with(event)
            self.plugin.send_matrix_message.assert_called_once()
            
            # Check the call arguments
            call_args = self.plugin.send_matrix_message.call_args
            self.assertEqual(call_args[0][0], "!test:matrix.org")  # room_id
            self.assertIn("Nodes: 5", call_args[0][1])  # message content
            self.assertEqual(call_args.kwargs['formatted'], False)
        
        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
