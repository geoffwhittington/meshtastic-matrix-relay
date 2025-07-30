#!/usr/bin/env python3
"""
Test suite for the MMRelay weather plugin.

Tests the weather forecast functionality including:
- Weather API integration with Open-Meteo
- Temperature unit conversion (metric/imperial)
- Weather code to text/emoji mapping
- GPS location-based weather requests
- Direct message vs broadcast handling
- Channel enablement checking
- Error handling for API failures
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.weather_plugin import Plugin


class TestWeatherPlugin(unittest.TestCase):
    """Test cases for the weather plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        self.plugin.config = {"units": "metric"}
        
        # Mock the is_channel_enabled method
        self.plugin.is_channel_enabled = MagicMock(return_value=True)
        
        # Mock the get_response_delay method
        self.plugin.get_response_delay = MagicMock(return_value=1.0)
        
        # Sample weather API response
        self.sample_weather_data = {
            "current_weather": {
                "temperature": 22.5,
                "weathercode": 1,
                "is_day": 1
            },
            "hourly": {
                "temperature_2m": [22.5, 22.0, 21.5, 21.0, 20.5, 20.0, 19.5, 19.0],
                "precipitation_probability": [10, 15, 20, 25, 30, 35, 40, 45],
                "weathercode": [1, 2, 3, 61, 63, 65, 71, 73]
            }
        }

    def test_plugin_name(self):
        """Test that plugin name is correctly set."""
        self.assertEqual(self.plugin.plugin_name, "weather")

    def test_description_property(self):
        """Test that description property returns expected string."""
        description = self.plugin.description
        self.assertEqual(description, "Show weather forecast for a radio node using GPS location")

    def test_get_matrix_commands(self):
        """Test that get_matrix_commands returns empty list."""
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, [])

    def test_get_mesh_commands(self):
        """Test that get_mesh_commands returns plugin name."""
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, ["weather"])

    def test_handle_room_message_always_false(self):
        """Test that handle_room_message always returns False."""
        async def run_test():
            result = await self.plugin.handle_room_message(None, None, "message")
            self.assertFalse(result)
        
        import asyncio
        asyncio.run(run_test())

    @patch('requests.get')
    def test_generate_forecast_metric_units(self, mock_get):
        """Test weather forecast generation with metric units."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response
        
        self.plugin.config = {"units": "metric"}
        
        forecast = self.plugin.generate_forecast(40.7128, -74.0060)
        
        # Should make API request with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        self.assertIn("latitude=40.7128", call_args)
        self.assertIn("longitude=-74.006", call_args)  # May be formatted without trailing zero
        self.assertIn("api.open-meteo.com", call_args)
        
        # Should contain current weather
        self.assertIn("Now: 🌤️ Mainly clear", forecast)
        self.assertIn("22.5°C", forecast)
        
        # Should contain 2h forecast (weathercode 3 = Overcast)
        self.assertIn("+2h: ☁️ Overcast", forecast)
        self.assertIn("21.5°C", forecast)
        self.assertIn("20%", forecast)

        # Should contain 5h forecast (weathercode 65 = Heavy rain)
        self.assertIn("+5h: 🌧️ Heavy rain", forecast)
        self.assertIn("20.0°C", forecast)  # Index 5 in temperature array
        self.assertIn("35%", forecast)

    @patch('requests.get')
    def test_generate_forecast_imperial_units(self, mock_get):
        """Test weather forecast generation with imperial units."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response
        
        self.plugin.config = {"units": "imperial"}
        
        forecast = self.plugin.generate_forecast(40.7128, -74.0060)
        
        # Should convert temperatures to Fahrenheit
        # 22.5°C = 72.5°F, 21.5°C = 70.7°F, 20.5°C = 68.9°F (but rounded to 68.0°F)
        self.assertIn("72.5°F", forecast)
        self.assertIn("70.7°F", forecast)
        self.assertIn("68.0°F", forecast)  # Rounded value

    @patch('requests.get')
    def test_generate_forecast_night_weather_codes(self, mock_get):
        """Test weather forecast generation with night weather codes."""
        night_weather_data = self.sample_weather_data.copy()
        night_weather_data["current_weather"]["is_day"] = 0  # Night time
        
        mock_response = MagicMock()
        mock_response.json.return_value = night_weather_data
        mock_get.return_value = mock_response
        
        forecast = self.plugin.generate_forecast(40.7128, -74.0060)
        
        # Should use night weather descriptions
        self.assertIn("🌙🌤️ Mainly clear", forecast)

    @patch('requests.get')
    def test_generate_forecast_unknown_weather_code(self, mock_get):
        """Test weather forecast generation with unknown weather code."""
        unknown_weather_data = self.sample_weather_data.copy()
        unknown_weather_data["current_weather"]["weathercode"] = 999  # Unknown code
        
        mock_response = MagicMock()
        mock_response.json.return_value = unknown_weather_data
        mock_get.return_value = mock_response
        
        forecast = self.plugin.generate_forecast(40.7128, -74.0060)
        
        # Should handle unknown weather codes gracefully
        self.assertIn("❓ Unknown", forecast)

    def test_handle_meshtastic_message_not_text_message(self):
        """Test handling non-text message."""
        packet = {
            "decoded": {
                "portnum": "TELEMETRY_APP",  # Not TEXT_MESSAGE_APP
                "data": "some data"
            }
        }
        
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)
        
        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_no_weather_command(self, mock_connect):
        """Test handling text message without weather command."""
        mock_client = MagicMock()
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Hello world"  # No !weather command
            },
            "channel": 0
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_channel_not_enabled(self, mock_connect):
        """Test handling message on disabled channel."""
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client

        self.plugin.is_channel_enabled = MagicMock(return_value=False)

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!weather"
            },
            "channel": 0
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)
            self.plugin.is_channel_enabled.assert_called_once_with(0, is_direct_message=False)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('requests.get')
    def test_handle_meshtastic_message_direct_message_with_location(self, mock_get, mock_connect):
        """Test handling direct message with node location."""
        # Mock weather API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response

        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {
            "!12345678": {
                "position": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
        }
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!weather"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 123456789  # Direct message to relay
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)

            # Should send direct message response
            mock_client.sendText.assert_called_once()
            call_args = mock_client.sendText.call_args
            self.assertEqual(call_args.kwargs['destinationId'], "!12345678")
            self.assertIn("Now: 🌤️ Mainly clear", call_args.kwargs['text'])

            # Should check if channel is enabled for direct message
            self.plugin.is_channel_enabled.assert_called_once_with(0, is_direct_message=True)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_broadcast_no_location(self, mock_connect):
        """Test handling broadcast message with no node location."""
        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {
            "!12345678": {
                # No position data
            }
        }
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!weather"
            },
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295  # BROADCAST_NUM
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)

            # Should send broadcast response with error message
            mock_client.sendText.assert_called_once()
            call_args = mock_client.sendText.call_args
            self.assertEqual(call_args.kwargs['channelIndex'], 0)
            self.assertEqual(call_args.kwargs['text'], "Cannot determine location")

            # Should check if channel is enabled for broadcast
            self.plugin.is_channel_enabled.assert_called_once_with(0, is_direct_message=False)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('requests.get')
    def test_handle_meshtastic_message_broadcast_with_location(self, mock_get, mock_connect):
        """Test handling broadcast message with node location."""
        # Mock weather API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response

        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {
            "!12345678": {
                "position": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
        }
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!weather please"
            },
            "channel": 1,
            "fromId": "!12345678",
            "to": 4294967295  # BROADCAST_NUM
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)

            # Should send broadcast response with weather data
            mock_client.sendText.assert_called_once()
            call_args = mock_client.sendText.call_args
            self.assertEqual(call_args.kwargs['channelIndex'], 1)
            self.assertIn("Now: 🌤️ Mainly clear", call_args.kwargs['text'])

            # Should check if channel is enabled for broadcast
            self.plugin.is_channel_enabled.assert_called_once_with(1, is_direct_message=False)

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_unknown_node(self, mock_connect):
        """Test handling message from unknown node."""
        # Mock meshtastic client with no nodes
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {}  # No nodes
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!weather"
            },
            "channel": 0,
            "fromId": "!unknown",
            "to": 4294967295
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return True but not send any message (node not found)
            self.assertTrue(result)
            mock_client.sendText.assert_not_called()

        import asyncio
        asyncio.run(run_test())

    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    def test_handle_meshtastic_message_missing_channel(self, mock_connect):
        """Test handling message with missing channel field."""
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!weather"
            },
            "fromId": "!12345678"
            # No channel field - should default to 0
        }

        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should use default channel 0
            self.plugin.is_channel_enabled.assert_called_once_with(0, is_direct_message=False)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
