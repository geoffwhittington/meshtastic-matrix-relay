#!/usr/bin/env python3
"""
Test suite for the MMRelay nodes plugin.

Tests the node listing functionality including:
- Relative time calculations
- Node data formatting and display
- Meshtastic client integration
- Matrix room message handling
- Device metrics parsing
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.nodes_plugin import Plugin, get_relative_time


class TestGetRelativeTime(unittest.TestCase):
    """Test cases for the get_relative_time utility function."""

    def test_get_relative_time_just_now(self):
        """Test relative time for very recent timestamps."""
        now = datetime.now()
        timestamp = now.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "Just now")

    def test_get_relative_time_minutes_ago(self):
        """Test relative time for timestamps within the last hour."""
        now = datetime.now()
        five_minutes_ago = now - timedelta(minutes=5)
        timestamp = five_minutes_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "5 minutes ago")

    def test_get_relative_time_one_minute_ago(self):
        """Test relative time for exactly one minute ago."""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        timestamp = one_minute_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "1 minutes ago")

    def test_get_relative_time_hours_ago(self):
        """Test relative time for timestamps within the last day."""
        now = datetime.now()
        three_hours_ago = now - timedelta(hours=3)
        timestamp = three_hours_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "3 hours ago")

    def test_get_relative_time_one_hour_ago(self):
        """Test relative time for exactly one hour ago."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        timestamp = one_hour_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "1 hours ago")

    def test_get_relative_time_days_ago(self):
        """Test relative time for timestamps within the last week."""
        now = datetime.now()
        three_days_ago = now - timedelta(days=3)
        timestamp = three_days_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "3 days ago")

    def test_get_relative_time_one_day_ago(self):
        """Test relative time for exactly one day ago."""
        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        timestamp = one_day_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "1 days ago")

    def test_get_relative_time_old_date(self):
        """Test relative time for timestamps older than 7 days."""
        now = datetime.now()
        ten_days_ago = now - timedelta(days=10)
        timestamp = ten_days_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        # Should return formatted date like "Jan 15, 2024"
        expected_format = ten_days_ago.strftime("%b %d, %Y")
        self.assertEqual(result, expected_format)

    def test_get_relative_time_exactly_seven_days(self):
        """Test relative time for exactly 7 days ago (boundary case)."""
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        timestamp = seven_days_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        self.assertEqual(result, "7 days ago")

    def test_get_relative_time_exactly_eight_days(self):
        """Test relative time for exactly 8 days ago (should use date format)."""
        now = datetime.now()
        eight_days_ago = now - timedelta(days=8)
        timestamp = eight_days_ago.timestamp()
        
        result = get_relative_time(timestamp)
        
        # Should return formatted date
        expected_format = eight_days_ago.strftime("%b %d, %Y")
        self.assertEqual(result, expected_format)


class TestNodesPlugin(unittest.TestCase):
    """Test cases for the nodes plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        
        # Mock Matrix client methods
        self.plugin.send_matrix_message = AsyncMock()
        
        # Mock meshtastic client with sample node data
        self.mock_meshtastic_client = MagicMock()
        self.mock_meshtastic_client.nodes = {
            "node1": {
                "user": {
                    "shortName": "N1",
                    "longName": "Node One",
                    "hwModel": "HELTEC_V3"
                },
                "snr": 12.5,
                "lastHeard": (datetime.now() - timedelta(minutes=5)).timestamp(),
                "deviceMetrics": {
                    "voltage": 4.2,
                    "batteryLevel": 85
                }
            },
            "node2": {
                "user": {
                    "shortName": "N2", 
                    "longName": "Node Two",
                    "hwModel": "TBEAM"
                },
                "snr": -8.0,
                "lastHeard": (datetime.now() - timedelta(hours=2)).timestamp(),
                "deviceMetrics": {
                    "voltage": 3.8,
                    "batteryLevel": 45
                }
            },
            "node3": {
                "user": {
                    "shortName": "N3",
                    "longName": "Node Three", 
                    "hwModel": "LORA32_V2_1"
                }
                # No SNR, lastHeard, or deviceMetrics data
            }
        }

    def test_plugin_name(self):
        """Test that plugin name is correctly set."""
        self.assertEqual(self.plugin.plugin_name, "nodes")

    def test_description_property(self):
        """Test that description property returns expected format."""
        description = self.plugin.description

        self.assertIn("Show mesh radios and node data", description)
        self.assertIn("$shortname $longname", description)
        self.assertIn("$devicemodel", description)
        self.assertIn("$battery $voltage", description)
        self.assertIn("$snr", description)
        self.assertIn("$lastseen", description)

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_full_data(self, mock_connect):
        """Test response generation with complete node data."""
        mock_connect.return_value = self.mock_meshtastic_client

        response = self.plugin.generate_response()

        # Should start with node count
        self.assertIn("Nodes: 3", response)

        # Should contain node information
        self.assertIn("N1 Node One", response)
        self.assertIn("N2 Node Two", response)
        self.assertIn("N3 Node Three", response)

        # Should contain hardware models
        self.assertIn("HELTEC_V3", response)
        self.assertIn("TBEAM", response)
        self.assertIn("LORA32_V2_1", response)

        # Should contain battery and voltage info for nodes with data
        self.assertIn("85%  4.2V", response)
        self.assertIn("45%  3.8V", response)

        # Should contain SNR info for nodes with data
        self.assertIn("12.5 dB ", response)
        self.assertIn("-8.0 dB ", response)

        # Should contain relative time info
        self.assertIn("minutes ago", response)
        self.assertIn("hours ago", response)

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_missing_data(self, mock_connect):
        """Test response generation with missing node data."""
        # Create a client with minimal node data
        minimal_client = MagicMock()
        minimal_client.nodes = {
            "node_minimal": {
                "user": {
                    "shortName": "MIN",
                    "longName": "Minimal Node",
                    "hwModel": "UNKNOWN"
                }
                # No SNR, lastHeard, or deviceMetrics
            }
        }
        mock_connect.return_value = minimal_client

        response = self.plugin.generate_response()

        # Should handle missing data gracefully
        self.assertIn("Nodes: 1", response)
        self.assertIn("MIN Minimal Node", response)
        self.assertIn("UNKNOWN", response)
        self.assertIn("?% ?V", response)  # Default values for missing battery/voltage
        self.assertIn("None", response)  # No last heard time

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_generate_response_with_null_values(self, mock_connect):
        """Test response generation with null values in node data."""
        null_client = MagicMock()
        null_client.nodes = {
            "node_null": {
                "user": {
                    "shortName": "NULL",
                    "longName": "Null Node",
                    "hwModel": "TEST"
                },
                "snr": None,
                "lastHeard": None,
                "deviceMetrics": {
                    "voltage": None,
                    "batteryLevel": None
                }
            }
        }
        mock_connect.return_value = null_client

        response = self.plugin.generate_response()

        # Should handle null values gracefully
        self.assertIn("Nodes: 1", response)
        self.assertIn("NULL Null Node", response)
        self.assertIn("?% ?V", response)  # Default values for null battery/voltage
        self.assertIn("None", response)  # No last heard time

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
        mock_connect.return_value = self.mock_meshtastic_client
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
            self.assertEqual(call_args.kwargs['room_id'], "!test:matrix.org")
            self.assertIn("Nodes: 3", call_args.kwargs['message'])
            self.assertEqual(call_args.kwargs['formatted'], False)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
