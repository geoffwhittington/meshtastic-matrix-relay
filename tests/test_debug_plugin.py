#!/usr/bin/env python3
"""
Test suite for the MMRelay debug plugin.

Tests the debug plugin functionality including:
- Packet logging and debugging
- Raw data stripping
- Message handling without interception
- Priority and configuration
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.debug_plugin import Plugin


class TestDebugPlugin(unittest.TestCase):
    """Test cases for the debug plugin functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()

    def test_plugin_name(self):
        """Test that the plugin has the correct name."""
        self.assertEqual(self.plugin.plugin_name, "debug")

    def test_plugin_priority(self):
        """Test that the plugin has the correct priority (should be 1 for early execution)."""
        self.assertEqual(self.plugin.priority, 1)

    def test_description_property(self):
        """Test that the plugin has a description."""
        # The debug plugin doesn't override the description property,
        # so it should return the default empty string from BasePlugin
        description = self.plugin.description
        self.assertEqual(description, "")

    @patch.object(Plugin, "strip_raw")
    def test_handle_meshtastic_message_logs_packet(self, mock_strip_raw):
        """Test that handle_meshtastic_message logs the packet after stripping raw data."""
        # Mock the strip_raw method to return a cleaned packet
        cleaned_packet = {"decoded": {"text": "test message"}, "fromId": "!12345678"}
        mock_strip_raw.return_value = cleaned_packet

        # Test packet
        original_packet = {
            "decoded": {"text": "test message", "raw": b"binary_data"},
            "fromId": "!12345678",
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                original_packet, "formatted_message", "TestNode", "TestMesh"
            )

            # Should call strip_raw with the original packet
            mock_strip_raw.assert_called_once_with(original_packet)

            # Should log the cleaned packet
            self.plugin.logger.debug.assert_called_once_with(
                f"Packet received: {cleaned_packet}"
            )

            # Should return False (never intercepts messages)
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    def test_handle_meshtastic_message_returns_false(self):
        """Test that handle_meshtastic_message always returns False (never intercepts)."""
        packet = {"decoded": {"text": "test message"}, "fromId": "!12345678"}

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    def test_handle_room_message_returns_false(self):
        """Test that handle_room_message always returns False (never intercepts)."""
        room = MagicMock()
        event = MagicMock()
        full_message = "test message"

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, full_message)
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    def test_handle_meshtastic_message_with_empty_packet(self):
        """Test that the plugin handles empty or minimal packets gracefully."""
        empty_packet = {}

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                empty_packet, "", "", ""
            )

            # Should still log the packet (even if empty)
            self.plugin.logger.debug.assert_called_once()

            # Should return False
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    def test_handle_meshtastic_message_with_complex_packet(self):
        """Test that the plugin handles complex packets with nested data."""
        complex_packet = {
            "decoded": {
                "text": "complex message",
                "portnum": 1,
                "payload": b"binary_payload",
            },
            "fromId": "!12345678",
            "toId": "!87654321",
            "channel": 0,
            "hopLimit": 3,
            "wantAck": True,
            "priority": 10,
            "rxTime": 1234567890,
            "rxSnr": -5.5,
            "rxRssi": -95,
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                complex_packet, "formatted_message", "TestNode", "TestMesh"
            )

            # Should log the packet
            self.plugin.logger.debug.assert_called_once()

            # Should return False
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    def test_plugin_never_intercepts_messages(self):
        """Test that the debug plugin never intercepts messages, allowing other plugins to process them."""
        # This is a behavioral test to ensure the plugin always returns False
        # from both message handling methods, which is critical for its role as a debug tool

        packet = {"decoded": {"text": "!important_command"}, "fromId": "!12345678"}
        room = MagicMock()
        event = MagicMock()

        async def run_test():
            # Test meshtastic message handling
            meshtastic_result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            self.assertFalse(meshtastic_result)

            # Test matrix room message handling
            matrix_result = await self.plugin.handle_room_message(
                room, event, "!important_command"
            )
            self.assertFalse(matrix_result)

        import asyncio

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
