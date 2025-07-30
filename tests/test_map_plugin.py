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
import io
import math
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import PIL.Image
import s2sphere
import staticmaps
from nio import AsyncClient, UploadResponse

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
        """Set up test fixtures."""
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
        """Test latlng property."""
        self.assertEqual(self.text_label.latlng(), self.latlng)

    def test_bounds(self):
        """Test bounds calculation."""
        bounds = self.text_label.bounds()
        self.assertIsInstance(bounds, s2sphere.LatLngRect)

    def test_extra_pixel_bounds(self):
        """Test extra pixel bounds calculation."""
        bounds = self.text_label.extra_pixel_bounds()
        self.assertIsInstance(bounds, tuple)
        self.assertEqual(len(bounds), 4)
        # Check that bounds are reasonable
        self.assertGreater(bounds[0], 0)  # left
        self.assertGreater(bounds[1], 0)  # top
        self.assertGreater(bounds[2], 0)  # right

    @patch('staticmaps.PillowRenderer')
    def test_render_pillow(self, mock_renderer_class):
        """Test Pillow rendering."""
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

    @patch('staticmaps.SvgRenderer')
    def test_render_svg(self, mock_renderer_class):
        """Test SVG rendering."""
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
        """Test textsize function."""
        mock_draw = MagicMock()
        mock_draw.textbbox.return_value = (0, 0, 100, 20)
        
        width, height = textsize(mock_draw, "Test text")
        
        self.assertEqual(width, 100)
        self.assertEqual(height, 20)
        mock_draw.textbbox.assert_called_once_with((0, 0), "Test text")


class TestAnonymizeLocation(unittest.TestCase):
    """Test cases for location anonymization."""

    def test_anonymize_location_default_radius(self):
        """Test location anonymization with default radius."""
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
        """Test location anonymization with custom radius."""
        lat, lon = 37.7749, -122.4194
        radius = 5000  # 5km
        new_lat, new_lon = anonymize_location(lat, lon, radius)
        
        # Check that coordinates changed
        self.assertNotEqual(new_lat, lat)
        self.assertNotEqual(new_lon, lon)
        
        # Check that change is within expected bounds
        lat_diff = abs(new_lat - lat)
        lon_diff = abs(new_lon - lon)
        self.assertLess(lat_diff, 0.05)  # Roughly 5km in degrees

    def test_anonymize_location_zero_radius(self):
        """Test location anonymization with zero radius."""
        lat, lon = 37.7749, -122.4194
        new_lat, new_lon = anonymize_location(lat, lon, 0)
        
        # With zero radius, coordinates should be very close to original
        self.assertAlmostEqual(new_lat, lat, places=5)
        self.assertAlmostEqual(new_lon, lon, places=5)


class TestGetMap(unittest.TestCase):
    """Test cases for map generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_locations = [
            {"lat": 37.7749, "lon": -122.4194, "label": "SF"},
            {"lat": 37.7849, "lon": -122.4094, "label": "Oakland"},
        ]

    @patch('staticmaps.Context')
    def test_get_map_default_params(self, mock_context_class):
        """Test map generation with default parameters."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_context.render_pillow.return_value = MagicMock()
        
        result = get_map(self.test_locations)
        
        mock_context.set_tile_provider.assert_called_once()
        mock_context.set_zoom.assert_called_once_with(None)
        self.assertEqual(mock_context.add_object.call_count, len(self.test_locations))
        mock_context.render_pillow.assert_called_once_with(1000, 1000)

    @patch('staticmaps.Context')
    def test_get_map_custom_params(self, mock_context_class):
        """Test map generation with custom parameters."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_context.render_pillow.return_value = MagicMock()
        
        result = get_map(
            self.test_locations,
            zoom=10,
            image_size=(800, 600),
            anonymize=False,
            radius=2000
        )
        
        mock_context.set_zoom.assert_called_once_with(10)
        mock_context.render_pillow.assert_called_once_with(800, 600)

    @patch('mmrelay.plugins.map_plugin.anonymize_location')
    @patch('staticmaps.Context')
    def test_get_map_with_anonymization(self, mock_context_class, mock_anonymize):
        """Test map generation with location anonymization."""
        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_context.render_pillow.return_value = MagicMock()
        mock_anonymize.return_value = (37.7750, -122.4195)
        
        result = get_map(self.test_locations, anonymize=True, radius=5000)
        
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
        """Test image upload functionality."""
        async def run_test():
            # Mock image save
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"fake_image_data"

            with patch('io.BytesIO', return_value=mock_buffer):
                self.mock_client.upload.return_value = (self.mock_upload_response, None)

                result = await upload_image(self.mock_client, self.mock_image)

                self.assertEqual(result, self.mock_upload_response)
                self.mock_client.upload.assert_called_once()

        asyncio.run(run_test())

    def test_send_room_image(self):
        """Test sending image to room."""
        async def run_test():
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

    @patch('mmrelay.plugins.map_plugin.upload_image')
    @patch('mmrelay.plugins.map_plugin.send_room_image')
    def test_send_image(self, mock_send_room_image, mock_upload_image):
        """Test complete image sending workflow."""
        async def run_test():
            room_id = "!test:example.com"
            mock_upload_image.return_value = self.mock_upload_response

            await send_image(self.mock_client, room_id, self.mock_image)

            mock_upload_image.assert_called_once_with(client=self.mock_client, image=self.mock_image)
            mock_send_room_image.assert_called_once_with(
                self.mock_client, room_id, upload_response=self.mock_upload_response
            )

        asyncio.run(run_test())


class TestMapPlugin(unittest.TestCase):
    """Test cases for the map Plugin class."""

    def setUp(self):
        """Set up test fixtures."""
        self.plugin = Plugin()
        self.plugin.config = {
            "zoom": 10,
            "image_width": 800,
            "image_height": 600,
            "anonymize": True,
            "radius": 2000,
        }

    def test_plugin_name(self):
        """Test plugin name property."""
        self.assertEqual(self.plugin.plugin_name, "map")

    def test_description(self):
        """Test plugin description."""
        description = self.plugin.description
        self.assertIn("Map of mesh radio nodes", description)
        self.assertIn("zoom", description)
        self.assertIn("size", description)

    def test_handle_meshtastic_message(self):
        """Test handling Meshtastic messages."""
        async def run_test():
            result = await self.plugin.handle_meshtastic_message(
                packet=MagicMock(),
                formatted_message="test",
                longname="Test User",
                meshnet_name="TestNet"
            )
            self.assertFalse(result)

        asyncio.run(run_test())

    def test_get_matrix_commands(self):
        """Test getting Matrix commands."""
        commands = self.plugin.get_matrix_commands()
        self.assertEqual(commands, ["map"])

    def test_get_mesh_commands(self):
        """Test getting mesh commands."""
        commands = self.plugin.get_mesh_commands()
        self.assertEqual(commands, [])

    @patch('mmrelay.plugins.map_plugin.send_image')
    @patch('mmrelay.plugins.map_plugin.get_map')
    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_room_message_basic_map(self, mock_connect_matrix, mock_connect_meshtastic, mock_get_map, mock_send_image):
        """Test handling basic map command."""
        async def run_test():
            # Setup mocks
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
                    "user": {"shortName": "SF"}
                }
            }
            mock_connect_meshtastic.return_value = mock_meshtastic_client

            mock_image = MagicMock()
            mock_get_map.return_value = mock_image

            # Mock the matches method to return True
            with patch.object(self.plugin, 'matches', return_value=True):
                result = await self.plugin.handle_room_message(mock_room, mock_event, "user: !map")

            self.assertTrue(result)
            mock_get_map.assert_called_once()
            mock_send_image.assert_called_once_with(mock_matrix_client, mock_room.room_id, mock_image)

        asyncio.run(run_test())

    @patch('mmrelay.plugins.map_plugin.send_image')
    @patch('mmrelay.plugins.map_plugin.get_map')
    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_room_message_with_zoom(self, mock_connect_matrix, mock_connect_meshtastic, mock_get_map, mock_send_image):
        """Test handling map command with zoom parameter."""
        async def run_test():
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

            with patch.object(self.plugin, 'matches', return_value=True):
                result = await self.plugin.handle_room_message(mock_room, mock_event, "user: !map zoom=15")

            self.assertTrue(result)
            # Check that get_map was called with zoom=15
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]['zoom'], 15)

        asyncio.run(run_test())

    @patch('mmrelay.plugins.map_plugin.send_image')
    @patch('mmrelay.plugins.map_plugin.get_map')
    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_room_message_with_size(self, mock_connect_matrix, mock_connect_meshtastic, mock_get_map, mock_send_image):
        """Test handling map command with size parameter."""
        async def run_test():
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

            with patch.object(self.plugin, 'matches', return_value=True):
                result = await self.plugin.handle_room_message(mock_room, mock_event, "user: !map size=500,400")

            self.assertTrue(result)
            # Check that get_map was called with correct image_size
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]['image_size'], (500, 400))

        asyncio.run(run_test())

    def test_handle_room_message_no_match(self):
        """Test handling non-map messages."""
        async def run_test():
            mock_room = MagicMock()
            mock_event = MagicMock()
            mock_event.body = "!help"

            with patch.object(self.plugin, 'matches', return_value=False):
                result = await self.plugin.handle_room_message(mock_room, mock_event, "!help")

            self.assertFalse(result)

        asyncio.run(run_test())

    @patch('mmrelay.plugins.map_plugin.send_image')
    @patch('mmrelay.plugins.map_plugin.get_map')
    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_room_message_invalid_zoom(self, mock_connect_matrix, mock_connect_meshtastic, mock_get_map, mock_send_image):
        """Test handling map command with invalid zoom parameter."""
        async def run_test():
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

            with patch.object(self.plugin, 'matches', return_value=True):
                result = await self.plugin.handle_room_message(mock_room, mock_event, "user: !map zoom=50")

            self.assertTrue(result)
            # Check that zoom was reset to default (8)
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]['zoom'], 8)

        asyncio.run(run_test())

    @patch('mmrelay.plugins.map_plugin.send_image')
    @patch('mmrelay.plugins.map_plugin.get_map')
    @patch('mmrelay.meshtastic_utils.connect_meshtastic')
    @patch('mmrelay.matrix_utils.connect_matrix')
    def test_handle_room_message_oversized_image(self, mock_connect_matrix, mock_connect_meshtastic, mock_get_map, mock_send_image):
        """Test handling map command with oversized image parameters."""
        async def run_test():
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

            with patch.object(self.plugin, 'matches', return_value=True):
                result = await self.plugin.handle_room_message(mock_room, mock_event, "user: !map size=2000,1500")

            self.assertTrue(result)
            # Check that image size was capped at 1000x1000
            call_args = mock_get_map.call_args
            self.assertEqual(call_args[1]['image_size'], (1000, 1000))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
