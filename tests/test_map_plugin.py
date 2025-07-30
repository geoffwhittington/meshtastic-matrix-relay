#!/usr/bin/env python3
"""
Test suite for map plugin functionality.

Tests the map generation plugin including:
- Map generation with various parameters
- Location anonymization
- Image upload and sending
- Command parsing and validation
- Configuration handling
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import s2sphere

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugins.map_plugin import (
    Plugin,
    TextLabel,
    anonymize_location,
    get_map,
    send_image,
    send_room_image,
    textsize,
    upload_image,
)


class TestTextLabel(unittest.TestCase):
    """Test cases for TextLabel class."""

    def setUp(self):
        """
        Initialize a TextLabel instance with a San Francisco coordinate and label for use in tests.
        """
        self.latlng = s2sphere.LatLng.from_degrees(37.7749, -122.4194)  # San Francisco
        self.text_label = TextLabel(self.latlng, "Test Label", fontSize=12)

    def test_init(self):
        """Test TextLabel initialization."""
        self.assertEqual(self.text_label._latlng, self.latlng)
        self.assertEqual(self.text_label._text, "Test Label")
        self.assertEqual(self.text_label._font_size, 12)
        self.assertEqual(self.text_label._margin, 4)
        self.assertEqual(self.text_label._arrow, 16)

    def test_latlng(self):
        """
        Verify that the latlng property of the TextLabel instance returns the correct coordinate.
        """
        self.assertEqual(self.text_label.latlng(), self.latlng)

    def test_bounds(self):
        """
        Test that the bounds() method returns an s2sphere.LatLngRect instance for the TextLabel.
        """
        bounds = self.text_label.bounds()
        self.assertIsInstance(bounds, s2sphere.LatLngRect)

    def test_extra_pixel_bounds(self):
        """
        Test that extra_pixel_bounds returns a 4-tuple of positive values representing the label's pixel bounds.
        """
        bounds = self.text_label.extra_pixel_bounds()
        self.assertIsInstance(bounds, tuple)
        self.assertEqual(len(bounds), 4)
        # Check that bounds are reasonable
        self.assertGreater(bounds[0], 0)  # left
        self.assertGreater(bounds[1], 0)  # top
        self.assertGreater(bounds[2], 0)  # right

    @patch("staticmaps.PillowRenderer")
    def test_render_pillow(self, mock_renderer_class):
        """
        Tests that the TextLabel's Pillow rendering method calls the expected drawing operations for polygon, line, and text.
        """
        mock_renderer = MagicMock()
        mock_transformer = MagicMock()
        mock_transformer.ll2pixel.return_value = (100, 100)
        mock_renderer.transformer.return_value = mock_transformer
        mock_renderer.offset_x.return_value = 0

        mock_draw = MagicMock()
        mock_draw.textbbox.return_value = (0, 0, 50, 12)
        mock_renderer.draw.return_value = mock_draw

        self.text_label.render_pillow(mock_renderer)

        # Verify drawing methods were called
        mock_draw.polygon.assert_called_once()
        mock_draw.line.assert_called_once()
        mock_draw.text.assert_called_once()

    @patch("staticmaps.SvgRenderer")
    def test_render_svg(self, mock_renderer_class):
        """
        Tests that the SVG rendering of a TextLabel creates the expected SVG path and text elements and adds them to the group.
        """
        mock_renderer = MagicMock()
        mock_transformer = MagicMock()
        mock_transformer.ll2pixel.return_value = (100, 100)
        mock_renderer.transformer.return_value = mock_transformer

        mock_drawing = MagicMock()
        mock_path = MagicMock()
        mock_drawing.path.return_value = mock_path
        mock_drawing.text.return_value = MagicMock()
        mock_renderer.drawing.return_value = mock_drawing

        mock_group = MagicMock()
        mock_renderer.group.return_value = mock_group

        self.text_label.render_svg(mock_renderer)

        # Verify SVG elements were created
        mock_drawing.path.assert_called_once()
        mock_drawing.text.assert_called_once()
        self.assertEqual(mock_group.add.call_count, 2)


class TestTextSizeFunction(unittest.TestCase):
    """Test cases for textsize function."""

    def test_textsize(self):
        """
        Tests that the textsize function returns the correct width and height based on the drawing context's text bounding box.
        """
        mock_draw = MagicMock()
        mock_draw.textbbox.return_value = (0, 0, 100, 20)

        width, height = textsize(mock_draw, "Test text")

        self.assertEqual(width, 100)
        self.assertEqual(height, 20)
        mock_draw.textbbox.assert_called_once_with((0, 0), "Test text")


class TestAnonymizeLocation(unittest.TestCase):
    """Test cases for location anonymization."""

    def test_anonymize_location_default_radius(self):
        """
        Verify that anonymize_location changes coordinates within approximately 1km when using the default radius.
        """
        lat, lon = 37.7749, -122.4194
        new_lat, new_lon = anonymize_location(lat, lon)

        # Check that coordinates changed
        self.assertNotEqual(new_lat, lat)
        self.assertNotEqual(new_lon, lon)

        # Check that change is within reasonable bounds (roughly 1km)
        lat_diff = abs(new_lat - lat)
        lon_diff = abs(new_lon - lon)
        self.assertLess(lat_diff, 0.01)  # Roughly 1km in degrees
        self.assertLess(lon_diff, 0.01)

    def test_anonymize_location_custom_radius(self):
        """
        Verify that anonymize_location modifies coordinates within a custom radius and that the changes remain within expected bounds.
        """
        lat, lon = 37.7749, -122.4194
        radius = 5000  # 5km
        new_lat, new_lon = anonymize_location(lat, lon, radius)

        # Check that coordinates changed
        self.assertNotEqual(new_lat, lat)
        self.assertNotEqual(new_lon, lon)

        # Check that change is within expected bounds
        lat_diff = abs(new_lat - lat)
        abs(new_lon - lon)
        self.assertLess(lat_diff, 0.05)  # Roughly 5km in degrees

    def test_anonymize_location_zero_radius(self):
        """
        Verify that anonymizing a location with a zero radius returns coordinates nearly identical to the original.
        """
        lat, lon = 37.7749, -122.4194
        new_lat, new_lon = anonymize_location(lat, lon, 0)

        # With zero radius, coordinates should be very close to original
        self.assertAlmostEqual(new_lat, lat, places=5)
        self.assertAlmostEqual(new_lon, lon, places=5)


class TestGetMap(unittest.TestCase):
    """Test cases for map generation."""

    def setUp(self):
        """
        Initialize test locations for use in map-related test cases.
        """
        self.test_locations = [
            {"lat": 37.7749, "lon": -122.4194, "label": "SF"},
            {"lat": 37.7849, "lon": -122.4094, "label": "Oakland"},
        ]

    @patch("staticmaps.Context")
    def test_get_map_default_params(self, mock_context_class):
        """
        Test that get_map generates a map with default zoom and image size, and adds all provided locations.
        """
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_context.render_pillow.return_value = MagicMock()

        get_map(self.test_locations)

        mock_context.set_tile_provider.assert_called_once()
        mock_context.set_zoom.assert_called_once_with(None)
        self.assertEqual(mock_context.add_object.call_count, len(self.test_locations))
        mock_context.render_pillow.assert_called_once_with(1000, 1000)

    @patch("staticmaps.Context")
    def test_get_map_custom_params(self, mock_context_class):
        """
        Tests that get_map generates a map image using custom zoom, image size, anonymization, and radius parameters.
        """
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_context.render_pillow.return_value = MagicMock()

        get_map(
            self.test_locations,
            zoom=10,
            image_size=(800, 600),
            anonymize=False,
            radius=2000,
        )

        mock_context.set_zoom.assert_called_once_with(10)
        mock_context.render_pillow.assert_called_once_with(800, 600)

    @patch("mmrelay.plugins.map_plugin.anonymize_location")
    @patch("staticmaps.Context")
    def test_get_map_with_anonymization(self, mock_context_class, mock_anonymize):
        """
        Tests that `get_map` calls the anonymization function for each location when anonymization is enabled and a radius is specified.
        """
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_context.render_pillow.return_value = MagicMock()
        mock_anonymize.return_value = (37.7750, -122.4195)

        get_map(self.test_locations, anonymize=True, radius=5000)

        # Should call anonymize_location for each location
        self.assertEqual(mock_anonymize.call_count, len(self.test_locations))
        mock_anonymize.assert_any_call(lat=37.7749, lon=-122.4194, radius=5000)


class TestImageUploadAndSend(unittest.TestCase):
    """Test cases for image upload and sending functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()
        self.mock_image = MagicMock()
        self.mock_upload_response = MagicMock()
        self.mock_upload_response.content_uri = "mxc://example.com/test123"

    def test_upload_image(self):
        """
        Test that the image upload function correctly saves the image to a buffer, uploads it using the client, and returns the upload response.
        """

        async def run_test():
            # Mock image save
            """
            Asynchronously tests the upload_image function to ensure it uploads an image using the client and returns the expected upload response.
            """
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"fake_image_data"

            with patch("io.BytesIO", return_value=mock_buffer):
                self.mock_client.upload.return_value = (self.mock_upload_response, None)

                result = await upload_image(self.mock_client, self.mock_image)

                self.assertEqual(result, self.mock_upload_response)
                self.mock_client.upload.assert_called_once()

        asyncio.run(run_test())

    def test_send_room_image(self):
        """
        Test that send_room_image sends an image message to the specified room with the correct content using the client.
        """

        async def run_test():
            """
            Asynchronously tests that an image is sent to a Matrix room with the correct message content.
            """
            room_id = "!test:example.com"

            await send_room_image(self.mock_client, room_id, self.mock_upload_response)

            self.mock_client.room_send.assert_called_once_with(
                room_id=room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.image",
                    "url": "mxc://example.com/test123",
                    "body": "image.png",
                },
            )

        asyncio.run(run_test())

    @patch("mmrelay.plugins.map_plugin.upload_image")
    @patch("mmrelay.plugins.map_plugin.send_room_image")
    def test_send_image(self, mock_send_room_image, mock_upload_image):
        """
        Test that the image sending workflow uploads an image and sends it to the specified room.

        Verifies that `upload_image` is called with the correct client and image, and that `send_room_image` is called with the resulting upload response.
        """

        async def run_test():
            """
            Asynchronously tests the image sending workflow by verifying that image upload and room image sending functions are called with the correct arguments.
            """
            room_id = "!test:example.com"
            mock_upload_image.return_value = self.mock_upload_response

            await send_image(self.mock_client, room_id, self.mock_image)

            mock_upload_image.assert_called_once_with(
                client=self.mock_client, image=self.mock_image
            )
            mock_send_room_image.assert_called_once_with(
                self.mock_client, room_id, upload_response=self.mock_upload_response
            )

        asyncio.run(run_test())


class TestMapPlugin(unittest.TestCase):
    """Test cases for the map Plugin class."""

    def setUp(self):
        """
        Initializes a Plugin instance and sets its configuration for use in tests.
        """
        self.plugin = Plugin()
        self.plugin.config = {
            "zoom": 10,
            "image_width": 800,
            "image_height": 600,
            "anonymize": True,
            "radius": 2000,
        }

    def test_plugin_name(self):
        """
        Test that the plugin_name property returns the expected value "map".
        """
        self.assertEqual(self.plugin.plugin_name, "map")

    def test_description(self):
        """
        Verifies that the plugin's description contains expected keywords related to map functionality.
        """
        description = self.plugin.description
        self.assertIn("Map of mesh radio nodes", description)
        self.assertIn("zoom", description)
        self.assertIn("size", description)

    def test_handle_meshtastic_message(self):
        """
        Tests that handle_meshtastic_message returns False when called with a Meshtastic message.
        """

        async def run_test():
            """
            Asynchronously tests that the plugin's `handle_meshtastic_message` method returns False when invoked with a sample message.
            """
            result = await self.plugin.handle_meshtastic_message(
                packet=MagicMock(),
                formatted_message="test",
                longname="Test User",
                meshnet_name="TestNet",
            )
            self.assertFalse(result)

        asyncio.run(run_test())

    def test_get_matrix_commands(self):
        """
        Test that the plugin returns the correct list of Matrix commands.
        """
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, ["map"])

    def test_get_mesh_commands(self):
        """
        Test that the plugin returns an empty list for mesh commands.
        """
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, [])

    @patch("mmrelay.plugins.map_plugin.send_image")
    @patch("mmrelay.plugins.map_plugin.get_map")
    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_room_message_basic_map(
        self,
        mock_connect_matrix,
        mock_connect_meshtastic,
        mock_get_map,
        mock_send_image,
    ):
        """
        Test that the plugin correctly handles a basic "!map" command in a Matrix room message.

        Verifies that the map is generated and sent when the command matches, and that the appropriate methods are called with the expected arguments.
        """

        async def run_test():
            # Setup mocks
            """
            Asynchronously tests that the plugin handles a "!map" room message by generating a map and sending the resulting image.

            This test verifies that when a "!map" command is received, the plugin correctly matches the command, generates a map image using node positions, and sends the image to the specified Matrix room.
            """
            mock_room = MagicMock()
            mock_room.room_id = "!test:example.com"
            mock_event = MagicMock()
            mock_event.body = "!map"

            mock_matrix_client = AsyncMock()
            mock_connect_matrix.return_value = mock_matrix_client

            mock_meshtastic_client = MagicMock()
            mock_meshtastic_client.nodes = {
                "node1": {
                    "position": {"latitude": 37.7749, "longitude": -122.4194},
                    "user": {"shortName": "SF"},
                }
            }
            mock_connect_meshtastic.return_value = mock_meshtastic_client

            mock_image = MagicMock()
            mock_get_map.return_value = mock_image

            # Mock the matches method to return True
            with patch.object(self.plugin, "matches", return_value=True):
                result = await self.plugin.handle_room_message(
                    mock_room, mock_event, "user: !map"
                )

            self.assertTrue(result)
            mock_get_map.assert_called_once()
            mock_send_image.assert_called_once_with(
                mock_matrix_client, mock_room.room_id, mock_image
            )

        asyncio.run(run_test())

    @patch("mmrelay.plugins.map_plugin.send_image")
    @patch("mmrelay.plugins.map_plugin.get_map")
    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_room_message_with_zoom(
        self,
        mock_connect_matrix,
        mock_connect_meshtastic,
        mock_get_map,
        mock_send_image,
    ):
        """
        Test that the plugin correctly handles a "!map" command with a specified zoom parameter.

        Verifies that when a room message includes "zoom=15", the plugin parses the zoom value and passes it to the map generation function.
        """

        async def run_test():
            """
            Asynchronously tests that the plugin handles a "!map zoom=15" command by generating a map with the specified zoom level.

            This test mocks the Matrix and Meshtastic clients, simulates a room message event, and verifies that the map generation function is called with the correct zoom parameter. It asserts that the plugin's message handler returns True, indicating successful handling.
            """
            mock_room = MagicMock()
            mock_room.room_id = "!test:example.com"
            mock_event = MagicMock()
            mock_event.body = "!map zoom=15"

            mock_matrix_client = AsyncMock()
            mock_connect_matrix.return_value = mock_matrix_client

            mock_meshtastic_client = MagicMock()
            mock_meshtastic_client.nodes = {}
            mock_connect_meshtastic.return_value = mock_meshtastic_client

            mock_image = MagicMock()
            mock_get_map.return_value = mock_image

            with patch.object(self.plugin, "matches", return_value=True):
                result = await self.plugin.handle_room_message(
                    mock_room, mock_event, "user: !map zoom=15"
                )

            self.assertTrue(result)
            # Check that get_map was called with zoom=15
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]["zoom"], 15)

        asyncio.run(run_test())

    @patch("mmrelay.plugins.map_plugin.send_image")
    @patch("mmrelay.plugins.map_plugin.get_map")
    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_room_message_with_size(
        self,
        mock_connect_matrix,
        mock_connect_meshtastic,
        mock_get_map,
        mock_send_image,
    ):
        """
        Tests that the map plugin correctly handles the "!map" command with a custom image size parameter, ensuring the generated map uses the specified dimensions.
        """

        async def run_test():
            """
            Asynchronously tests that the plugin handles a "!map size=500,400" command by generating a map image with the specified size and returns True.

            This test verifies that the `get_map` function is called with the correct `image_size` parameter when the command includes a custom size.
            """
            mock_room = MagicMock()
            mock_room.room_id = "!test:example.com"
            mock_event = MagicMock()
            mock_event.body = "!map size=500,400"

            mock_matrix_client = AsyncMock()
            mock_connect_matrix.return_value = mock_matrix_client

            mock_meshtastic_client = MagicMock()
            mock_meshtastic_client.nodes = {}
            mock_connect_meshtastic.return_value = mock_meshtastic_client

            mock_image = MagicMock()
            mock_get_map.return_value = mock_image

            with patch.object(self.plugin, "matches", return_value=True):
                result = await self.plugin.handle_room_message(
                    mock_room, mock_event, "user: !map size=500,400"
                )

            self.assertTrue(result)
            # Check that get_map was called with correct image_size
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]["image_size"], (500, 400))

        asyncio.run(run_test())

    def test_handle_room_message_no_match(self):
        """
        Test that handle_room_message returns False when the message does not match the map command.
        """

        async def run_test():
            """
            Asynchronously tests that the plugin's handle_room_message method returns False when the message does not match the plugin command.
            """
            mock_room = MagicMock()
            mock_event = MagicMock()
            mock_event.body = "!help"

            with patch.object(self.plugin, "matches", return_value=False):
                result = await self.plugin.handle_room_message(
                    mock_room, mock_event, "!help"
                )

            self.assertFalse(result)

        asyncio.run(run_test())

    @patch("mmrelay.plugins.map_plugin.send_image")
    @patch("mmrelay.plugins.map_plugin.get_map")
    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_room_message_invalid_zoom(
        self,
        mock_connect_matrix,
        mock_connect_meshtastic,
        mock_get_map,
        mock_send_image,
    ):
        """
        Test that the plugin resets an invalid zoom parameter to the default value when handling a map command.

        Verifies that when a map command with an out-of-range zoom value is received, the plugin uses the default zoom (8) for map generation.
        """

        async def run_test():
            """
            Asynchronously tests that an invalid zoom parameter in the "!map" command is reset to the default value when handling a room message.

            The test mocks Matrix and Meshtastic clients, simulates a "!map zoom=50" command, and verifies that the map generation function is called with the default zoom level (8) instead of the invalid value.
            """
            mock_room = MagicMock()
            mock_room.room_id = "!test:example.com"
            mock_event = MagicMock()
            mock_event.body = "!map zoom=50"  # Invalid zoom > 30

            mock_matrix_client = AsyncMock()
            mock_connect_matrix.return_value = mock_matrix_client

            mock_meshtastic_client = MagicMock()
            mock_meshtastic_client.nodes = {}
            mock_connect_meshtastic.return_value = mock_meshtastic_client

            mock_image = MagicMock()
            mock_get_map.return_value = mock_image

            with patch.object(self.plugin, "matches", return_value=True):
                result = await self.plugin.handle_room_message(
                    mock_room, mock_event, "user: !map zoom=50"
                )

            self.assertTrue(result)
            # Check that zoom was reset to default (8)
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]["zoom"], 8)

        asyncio.run(run_test())

    @patch("mmrelay.plugins.map_plugin.send_image")
    @patch("mmrelay.plugins.map_plugin.get_map")
    @patch("mmrelay.meshtastic_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.connect_matrix")
    def test_handle_room_message_oversized_image(
        self,
        mock_connect_matrix,
        mock_connect_meshtastic,
        mock_get_map,
        mock_send_image,
    ):
        """
        Test that the map command with oversized image size parameters results in the image size being capped at 1000x1000 pixels.

        Verifies that when a user requests an image size exceeding the allowed maximum, the plugin enforces the size limit before generating the map.
        """

        async def run_test():
            """
            Test that oversized image size parameters in the "!map" command are capped at the maximum allowed dimensions when handling a room message.

            Asserts that the plugin processes the command, generates a map image with the capped size, and returns True.
            """
            mock_room = MagicMock()
            mock_room.room_id = "!test:example.com"
            mock_event = MagicMock()
            mock_event.body = "!map size=2000,1500"  # Oversized

            mock_matrix_client = AsyncMock()
            mock_connect_matrix.return_value = mock_matrix_client

            mock_meshtastic_client = MagicMock()
            mock_meshtastic_client.nodes = {}
            mock_connect_meshtastic.return_value = mock_meshtastic_client

            mock_image = MagicMock()
            mock_get_map.return_value = mock_image

            with patch.object(self.plugin, "matches", return_value=True):
                result = await self.plugin.handle_room_message(
                    mock_room, mock_event, "user: !map size=2000,1500"
                )

            self.assertTrue(result)
            # Check that image size was capped at 1000x1000
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]["image_size"], (1000, 1000))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
