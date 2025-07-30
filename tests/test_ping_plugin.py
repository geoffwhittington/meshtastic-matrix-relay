#!/usr/bin/env python3
"""
Test suite for the MMRelay ping plugin.

Tests the ping/pong functionality including:
- Case matching utility function
- Ping detection with various punctuation patterns
- Direct message vs broadcast handling
- Response delay and message routing
- Matrix room message handling
- Channel enablement checking
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.ping_plugin import Plugin, match_case


class TestMatchCase(unittest.TestCase):
    """Test cases for the match_case utility function."""

    def test_match_case_all_lowercase(self):
        """Test match_case with all lowercase source."""
        result = match_case("ping", "pong")
        self.assertEqual(result, "pong")

    def test_match_case_all_uppercase(self):
        """Test match_case with all uppercase source."""
        result = match_case("PING", "pong")
        self.assertEqual(result, "PONG")

    def test_match_case_mixed_case(self):
        """Test match_case with mixed case source."""
        result = match_case("PiNg", "pong")
        self.assertEqual(result, "PoNg")

    def test_match_case_first_letter_uppercase(self):
        """Test match_case with first letter uppercase."""
        result = match_case("Ping", "pong")
        self.assertEqual(result, "Pong")

    def test_match_case_different_lengths(self):
        """Test match_case with different length strings."""
        result = match_case("Pi", "pong")
        self.assertEqual(result, "Po")

    def test_match_case_empty_strings(self):
        """Test match_case with empty strings."""
        result = match_case("", "pong")
        self.assertEqual(result, "")


class TestPingPlugin(unittest.TestCase):
    """Test cases for the ping plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        
        # Mock the is_channel_enabled method
        self.plugin.is_channel_enabled = MagicMock(return_value=True)
        
        # Mock the get_response_delay method
        self.plugin.get_response_delay = MagicMock(return_value=1.0)
        
        # Mock Matrix client methods
        self.plugin.send_matrix_message = AsyncMock()

    def test_plugin_name(self):
        """Test that plugin name is correctly set."""
        self.assertEqual(self.plugin.plugin_name, "ping")

    def test_description_property(self):
        """Test that description property returns expected string."""
        description = self.plugin.description
        self.assertEqual(description, "Check connectivity with the relay or respond to pings over the mesh")

    def test_get_matrix_commands(self):
        """Test that get_matrix_commands returns ping command."""
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, ["ping"])

    def test_get_mesh_commands(self):
        """Test that get_mesh_commands returns ping command."""
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, ["ping"])

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('asyncio.sleep')
    def test_handle_meshtastic_message_simple_ping_broadcast(self, mock_sleep, mock_connect):
        """Test handling simple ping message as broadcast."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        packet = {
            "decoded": {
                "text": "ping"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295  # BROADCAST_NUM
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertTrue(result)
            
            # Should check channel enablement for broadcast
            self.plugin.is_channel_enabled.assert_called_once_with(0, is_direct_message=False)
            
            # Should wait for response delay
            mock_sleep.assert_called_once_with(1.0)
            
            # Should send broadcast response
            mock_client.sendText.assert_called_once_with(text="pong", channelIndex=0)
            
            # Should log processing
            self.plugin.logger.info.assert_called_once()
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('asyncio.sleep')
    def test_handle_meshtastic_message_ping_direct_message(self, mock_sleep, mock_connect):
        """Test handling ping message as direct message."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        packet = {
            "decoded": {
                "text": "ping"
            },
            "channel": 1,
            "fromId": "!12345678",
            "to": 123456789  # Direct to relay
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertTrue(result)
            
            # Should check channel enablement for direct message
            self.plugin.is_channel_enabled.assert_called_once_with(1, is_direct_message=True)
            
            # Should send direct message response
            mock_client.sendText.assert_called_once_with(
                text="pong", destinationId="!12345678"
            )
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('asyncio.sleep')
    def test_handle_meshtastic_message_ping_with_punctuation(self, mock_sleep, mock_connect):
        """Test handling ping message with punctuation."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        packet = {
            "decoded": {
                "text": "!ping!"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295  # BROADCAST_NUM
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertTrue(result)
            
            # Should preserve punctuation in response
            mock_client.sendText.assert_called_once_with(text="!pong!", channelIndex=0)
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('asyncio.sleep')
    def test_handle_meshtastic_message_ping_excessive_punctuation(self, mock_sleep, mock_connect):
        """Test handling ping message with excessive punctuation."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        packet = {
            "decoded": {
                "text": "!!!ping!!!"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295  # BROADCAST_NUM
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertTrue(result)
            
            # Should use "Pong..." for excessive punctuation (>5 chars)
            mock_client.sendText.assert_called_once_with(text="Pong...", channelIndex=0)
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('asyncio.sleep')
    def test_handle_meshtastic_message_ping_case_matching(self, mock_sleep, mock_connect):
        """Test handling ping message with case matching."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        packet = {
            "decoded": {
                "text": "PING"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295  # BROADCAST_NUM
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertTrue(result)
            
            # Should match case of original ping
            mock_client.sendText.assert_called_once_with(text="PONG", channelIndex=0)
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_no_ping(self, mock_connect):
        """Test handling message without ping."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        packet = {
            "decoded": {
                "text": "Hello world"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertFalse(result)
            
            # Should not send any message
            mock_client.sendText.assert_not_called()
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_channel_disabled(self, mock_connect):
        """Test handling ping when channel is disabled."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client
        
        # Mock channel as disabled
        self.plugin.is_channel_enabled = MagicMock(return_value=False)
        
        packet = {
            "decoded": {
                "text": "ping"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )
            
            self.assertFalse(result)
            
            # Should not send any message
            mock_client.sendText.assert_not_called()
        
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

    def test_handle_room_message_ping_match(self):
        """Test handle_room_message with ping command match."""
        self.plugin.matches = MagicMock(return_value=True)

        room = MagicMock()
        room.room_id = "!test:matrix.org"
        event = MagicMock()

        async def run_test():
            result = await self.plugin.handle_room_message(room, event, "bot: !ping")

            self.assertTrue(result)
            self.plugin.matches.assert_called_once_with(event)
            self.plugin.send_matrix_message.assert_called_once_with("!test:matrix.org", "pong!")

        import asyncio
        asyncio.run(run_test())

    def test_handle_meshtastic_message_no_decoded(self):
        """Test handling packet without decoded field."""
        packet = {
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )

            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())

    def test_handle_meshtastic_message_no_text(self):
        """Test handling packet without text field."""
        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "TestNode", "TestMesh"
            )

            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
