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
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.weather_plugin import Plugin


class TestWeatherPlugin(unittest.TestCase):
    """Test cases for the weather plugin."""

    def setUp(self):
        """
        Initialize the test environment for each test case by creating a Plugin instance with mocked dependencies and sample weather data.
        """
        self.plugin = Plugin()
        self.plugin.logger = MagicMock()
        self.plugin.config = {"units": "metric"}

        # Mock the is_channel_enabled method
        self.plugin.is_channel_enabled = MagicMock(return_value=True)

        # Mock the get_response_delay method
        self.plugin.get_response_delay = MagicMock(return_value=1.0)

        # Sample weather API response
        self.sample_weather_data = {
            "current_weather": {"temperature": 22.5, "weathercode": 1, "is_day": 1},
            "hourly": {
                "temperature_2m": [22.5, 22.0, 21.5, 21.0, 20.5, 20.0, 19.5, 19.0],
                "precipitation_probability": [10, 15, 20, 25, 30, 35, 40, 45],
                "weathercode": [1, 2, 3, 61, 63, 65, 71, 73],
            },
        }

    def test_plugin_name(self):
        """
        Verify that the plugin's name is set to "weather".
        """
        self.assertEqual(self.plugin.plugin_name, "weather")

    def test_description_property(self):
        """
        Test that the plugin's description property returns the expected string.
        """
        description = self.plugin.description
        self.assertEqual(
            description, "Show weather forecast for a radio node using GPS location"
        )

    def test_get_matrix_commands(self):
        """
        Test that the plugin's get_matrix_commands method returns an empty list.
        """
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, [])

    def test_get_mesh_commands(self):
        """
        Test that the plugin's get_mesh_commands method returns the expected list of mesh commands.
        """
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, ["weather"])

    def test_handle_room_message_always_false(self):
        """
        Test that handle_room_message always returns False asynchronously.
        """

        async def run_test():
            """
            Asynchronously tests that handle_room_message always returns False when called.

            Returns:
                bool: False, indicating the message was not handled.
            """
            result = await self.plugin.handle_room_message(None, None, "message")
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    @patch("requests.get")
    def test_generate_forecast_metric_units(self, mock_get):
        """
        Test that the weather forecast is generated correctly using metric units.

        Verifies that the plugin requests weather data with the correct API parameters, parses the response, and formats the forecast string with Celsius temperatures, weather descriptions, emojis, and precipitation probabilities.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response

        self.plugin.config = {"units": "metric"}

        forecast = self.plugin.generate_forecast(40.7128, -74.0060)

        # Should make API request with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        self.assertIn("latitude=40.7128", call_args)
        self.assertIn(
            "longitude=-74.006", call_args
        )  # May be formatted without trailing zero
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

    @patch("requests.get")
    def test_generate_forecast_imperial_units(self, mock_get):
        """
        Test that the weather forecast is generated with temperatures converted to Fahrenheit when imperial units are configured.

        Verifies that the forecast output includes correctly converted and rounded Fahrenheit temperatures based on sample weather data.
        """
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

    @patch("requests.get")
    def test_generate_forecast_night_weather_codes(self, mock_get):
        """
        Test that the forecast generation uses night-specific weather descriptions and emojis when night weather codes are present in the API response.
        """
        night_weather_data = self.sample_weather_data.copy()
        night_weather_data["current_weather"]["is_day"] = 0  # Night time

        mock_response = MagicMock()
        mock_response.json.return_value = night_weather_data
        mock_get.return_value = mock_response

        forecast = self.plugin.generate_forecast(40.7128, -74.0060)

        # Should use night weather descriptions
        self.assertIn("🌙🌤️ Mainly clear", forecast)

    @patch("requests.get")
    def test_generate_forecast_unknown_weather_code(self, mock_get):
        """
        Test that the forecast generation handles unknown weather codes gracefully.

        Mocks the weather API response to include an unrecognized weather code and verifies that the generated forecast string indicates an unknown weather condition.
        """
        unknown_weather_data = self.sample_weather_data.copy()
        unknown_weather_data["current_weather"]["weathercode"] = 999  # Unknown code

        mock_response = MagicMock()
        mock_response.json.return_value = unknown_weather_data
        mock_get.return_value = mock_response

        forecast = self.plugin.generate_forecast(40.7128, -74.0060)

        # Should handle unknown weather codes gracefully
        self.assertIn("❓ Unknown", forecast)

    def test_handle_meshtastic_message_not_text_message(self):
        """
        Test that the plugin ignores Meshtastic messages that are not text messages.

        Verifies that handling a Meshtastic packet with a non-text port number results in the handler returning False.
        """
        packet = {
            "decoded": {
                "portnum": "TELEMETRY_APP",  # Not TEXT_MESSAGE_APP
                "data": "some data",
            }
        }

        async def run_test():
            """
            Runs an asynchronous test to verify that handling a Meshtastic message returns False.

            Returns:
                bool: False, indicating the message was not handled.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_handle_meshtastic_message_no_weather_command(self, mock_connect):
        """
        Test that a Meshtastic text message without the "!weather" command is ignored by the plugin.

        Verifies that the plugin's message handler returns False when processing a text message that does not contain the weather command.
        """
        mock_client = MagicMock()
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "Hello world",  # No !weather command
            },
            "channel": 0,
        }

        async def run_test():
            """
            Runs an asynchronous test to verify that handling a Meshtastic message returns False.

            Returns:
                bool: False, indicating the message was not handled.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_handle_meshtastic_message_channel_not_enabled(self, mock_connect):
        """
        Test that a "!weather" message on a disabled channel is not processed.

        Verifies that the plugin checks channel enablement, does not handle the message, and returns False when the channel is disabled.
        """
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client

        self.plugin.is_channel_enabled = MagicMock(return_value=False)

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!weather"},
            "channel": 0,
        }

        async def run_test():
            """
            Asynchronously runs a test to verify that handling a Meshtastic message returns False and checks channel enablement with default parameters.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )
            self.assertFalse(result)
            self.plugin.is_channel_enabled.assert_called_once_with(
                0, is_direct_message=False
            )

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("requests.get")
    def test_handle_meshtastic_message_direct_message_with_location(
        self, mock_get, mock_connect
    ):
        """
        Tests that a direct Meshtastic message containing the "!weather" command from a node with location data triggers a weather forecast response sent directly to the sender.

        Verifies that the plugin retrieves the node's GPS location, fetches weather data, generates a forecast, and sends a direct message reply. Also checks that channel enablement is validated for direct messages and that the correct recipient and forecast content are used in the response.
        """
        # Mock weather API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response

        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {
            "!12345678": {"position": {"latitude": 40.7128, "longitude": -74.0060}}
        }
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!weather"},
            "channel": 0,
            "fromId": "!12345678",
            "to": 123456789,  # Direct message to relay
        }

        async def run_test():
            """
            Asynchronously tests that a direct Meshtastic message containing a weather command from a known node with location data triggers the plugin to send a direct forecast response and checks channel enablement for direct messages.

            Verifies that the plugin returns True, sends a direct message with the expected weather forecast, and calls the channel enablement check with the correct parameters.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)

            # Should send direct message response
            mock_client.sendText.assert_called_once()
            call_args = mock_client.sendText.call_args
            self.assertEqual(call_args.kwargs["destinationId"], "!12345678")
            self.assertIn("Now: 🌤️ Mainly clear", call_args.kwargs["text"])

            # Should check if channel is enabled for direct message
            self.plugin.is_channel_enabled.assert_called_once_with(
                0, is_direct_message=True
            )

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_handle_meshtastic_message_broadcast_no_location(self, mock_connect):
        """
        Test that a broadcast "!weather" message from a node without location data results in an error response.

        Verifies that the plugin sends a broadcast message indicating it cannot determine the location and checks channel enablement for broadcast messages.
        """
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
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!weather"},
            "channel": 0,
            "fromId": "!12345678",
            "to": 4294967295,  # BROADCAST_NUM
        }

        async def run_test():
            """
            Asynchronously tests that the plugin responds with an error message when handling a broadcast weather request without location data.

            Verifies that the plugin sends a broadcast message indicating location cannot be determined, checks channel enablement for broadcast, and returns True.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)

            # Should send broadcast response with error message
            mock_client.sendText.assert_called_once()
            call_args = mock_client.sendText.call_args
            self.assertEqual(call_args.kwargs["channelIndex"], 0)
            self.assertEqual(call_args.kwargs["text"], "Cannot determine location")

            # Should check if channel is enabled for broadcast
            self.plugin.is_channel_enabled.assert_called_once_with(
                0, is_direct_message=False
            )

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("requests.get")
    def test_handle_meshtastic_message_broadcast_with_location(
        self, mock_get, mock_connect
    ):
        """
        Tests that a broadcast "!weather" message from a node with location data triggers a weather API request and sends a broadcast response with the forecast.

        Verifies that the plugin correctly retrieves the node's location, fetches weather data, formats the forecast, and sends it as a broadcast message on the appropriate channel. Also checks that channel enablement is respected for broadcast messages.
        """
        # Mock weather API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_weather_data
        mock_get.return_value = mock_response

        # Mock meshtastic client
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {
            "!12345678": {"position": {"latitude": 40.7128, "longitude": -74.0060}}
        }
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!weather please"},
            "channel": 1,
            "fromId": "!12345678",
            "to": 4294967295,  # BROADCAST_NUM
        }

        async def run_test():
            """
            Asynchronously tests that a broadcast "!weather" message with location data triggers a weather forecast response.

            Verifies that the plugin sends a broadcast message with the correct weather forecast, checks channel enablement for broadcast, and returns True.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            self.assertTrue(result)

            # Should send broadcast response with weather data
            mock_client.sendText.assert_called_once()
            call_args = mock_client.sendText.call_args
            self.assertEqual(call_args.kwargs["channelIndex"], 1)
            self.assertIn("Now: 🌤️ Mainly clear", call_args.kwargs["text"])

            # Should check if channel is enabled for broadcast
            self.plugin.is_channel_enabled.assert_called_once_with(
                1, is_direct_message=False
            )

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_handle_meshtastic_message_unknown_node(self, mock_connect):
        """
        Test that a weather request from an unknown node returns True without sending a response message.
        """
        # Mock meshtastic client with no nodes
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_client.nodes = {}  # No nodes
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!weather"},
            "channel": 0,
            "fromId": "!unknown",
            "to": 4294967295,
        }

        async def run_test():
            """
            Runs an asynchronous test to verify that handling a Meshtastic message from an unknown node returns True and does not send any message.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should return True but not send any message (node not found)
            self.assertTrue(result)
            mock_client.sendText.assert_not_called()

        import asyncio

        asyncio.run(run_test())

    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    def test_handle_meshtastic_message_missing_channel(self, mock_connect):
        """
        Test that handling a Meshtastic message without a channel field defaults to channel 0 and checks channel enablement accordingly.
        """
        mock_client = MagicMock()
        mock_client.myInfo.my_node_num = 123456789
        mock_connect.return_value = mock_client

        packet = {
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!weather"},
            "fromId": "!12345678",
            # No channel field - should default to 0
        }

        async def run_test():
            """
            Runs an asynchronous test to verify that handling a Meshtastic message without a channel field defaults to channel 0 and checks channel enablement accordingly.
            """
            await self.plugin.handle_meshtastic_message(
                packet, "formatted_message", "longname", "meshnet_name"
            )

            # Should use default channel 0
            self.plugin.is_channel_enabled.assert_called_once_with(
                0, is_direct_message=False
            )

        import asyncio

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
