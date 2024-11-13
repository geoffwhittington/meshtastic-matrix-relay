import io
import math
import re
import random

import s2sphere
import staticmaps
from nio import AsyncClient, UploadResponse
from PIL import Image

from plugins.base_plugin import BasePlugin
from log_utils import get_logger

# Initialize logger using log_utils.py
logger = get_logger(name="Plugin:map")


class TextLabel(staticmaps.Object):
    def __init__(self, latlng: s2sphere.LatLng, text: str, fontSize: int = 12) -> None:
        super().__init__()
        self._latlng = latlng
        self._text = text
        self._margin = 4
        self._arrow = 16
        self._font_size = fontSize

    def latlng(self) -> s2sphere.LatLng:
        return self._latlng

    def bounds(self) -> s2sphere.LatLngRect:
        return s2sphere.LatLngRect.from_point(self._latlng)

    def extra_pixel_bounds(self) -> staticmaps.PixelBoundsT:
        # Guess text extents.
        tw = len(self._text) * self._font_size * 0.5
        th = self._font_size * 1.2
        w = max(self._arrow, tw + 2.0 * self._margin)
        return (int(w / 2.0), int(th + 2.0 * self._margin + self._arrow), int(w / 2), 0)

    def render_pillow(self, renderer: staticmaps.PillowRenderer) -> None:
        x, y = renderer.transformer().ll2pixel(self.latlng())
        x = x + renderer.offset_x()

        tw, th = renderer.draw().textsize(self._text)
        w = max(self._arrow, tw + 2 * self._margin)
        h = th + 2 * self._margin

        path = [
            (x, y),
            (x + self._arrow / 2, y - self._arrow),
            (x + w / 2, y - self._arrow),
            (x + w / 2, y - self._arrow - h),
            (x - w / 2, y - self._arrow - h),
            (x - w / 2, y - self._arrow),
            (x - self._arrow / 2, y - self._arrow),
        ]

        renderer.draw().polygon(path, fill=(255, 255, 255, 255))
        renderer.draw().line(path, fill=(255, 0, 0, 255))
        renderer.draw().text(
            (x - tw / 2, y - self._arrow - h / 2 - th / 2),
            self._text,
            fill=(0, 0, 0, 255),
        )


def anonymize_location(lat, lon, radius=1000):
    # Convert latitude to radians for math.cos
    lat_rad = math.radians(lat)

    # Ensure math.cos(lat_rad) is not zero to avoid division by zero
    cos_lat = math.cos(lat_rad)
    if abs(cos_lat) < 1e-6:
        cos_lat = 1e-6  # Small value to prevent division by zero

    # Generate random offsets for latitude and longitude
    lat_offset = random.uniform(-radius / 111320, radius / 111320)
    lon_offset = random.uniform(
        -radius / (111320 * cos_lat), radius / (111320 * cos_lat)
    )

    # Apply the offsets to the location coordinates
    new_lat = lat + lat_offset
    new_lon = lon + lon_offset

    return new_lat, new_lon


def get_map(locations, zoom=None, image_size=None, anonymize=True, radius=10000):
    """
    Generate a map image with the given locations.
    """
    context = staticmaps.Context()

    # Use a tile provider with headers
    tile_provider = staticmaps.TileProvider(
        url="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution="© OpenStreetMap contributors",
        headers={"User-Agent": "MyApp/1.0"},
    )
    context.set_tile_provider(tile_provider)

    # Set default zoom if not provided
    if zoom is not None:
        context.set_zoom(zoom)

    for location in locations:
        if anonymize:
            new_location = anonymize_location(
                lat=float(location["lat"]),
                lon=float(location["lon"]),
                radius=radius,
            )
            radio = staticmaps.create_latlng(new_location[0], new_location[1])
        else:
            radio = staticmaps.create_latlng(
                float(location["lat"]), float(location["lon"])
            )
        context.add_object(TextLabel(radio, location["label"], fontSize=50))

    # Render the map with exception handling to prevent hanging
    try:
        if image_size:
            logger.debug(f"Rendering map with size {image_size}")
            image = context.render_pillow(image_size[0], image_size[1])
        else:
            logger.debug("Rendering map with default size 1000x1000")
            image = context.render_pillow(1000, 1000)
        return image
    except Exception as e:
        logger.error(f"Error rendering map: {e}")
        return None


async def upload_image(client: AsyncClient, image: Image.Image) -> UploadResponse:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_data = buffer.getvalue()

    response, maybe_keys = await client.upload(
        io.BytesIO(image_data),
        content_type="image/png",
        filename="location.png",
        filesize=len(image_data),
    )

    return response


async def send_room_image(
    client: AsyncClient, room_id: str, upload_response: UploadResponse
):
    await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={"msgtype": "m.image", "url": upload_response.content_uri, "body": ""},
    )


async def send_image(client: AsyncClient, room_id: str, image: Image.Image):
    if image is None:
        await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": "Failed to generate map image.",
            },
        )
    else:
        response = await upload_image(client=client, image=image)
        await send_room_image(client, room_id, upload_response=response)


class Plugin(BasePlugin):
    plugin_name = "map"

    @property
    def description(self):
        return (
            "Map of mesh radio nodes. Supports `zoom` and `size` options to customize"
        )

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        return False

    def get_matrix_commands(self):
        return [self.plugin_name]

    def get_mesh_commands(self):
        return []

    async def handle_room_message(self, room, event, full_message):
        full_message = full_message.strip()
        if not self.matches(full_message):
            return False

        from matrix_utils import connect_matrix
        from meshtastic_utils import connect_meshtastic

        matrix_client = await connect_matrix()
        meshtastic_client = connect_meshtastic()

        pattern = r"^.*:(?: !map(?: zoom=(\d+))?(?: size=(\d+),(\d+))?)?$"
        match = re.match(pattern, full_message)

        # Indicate this message is not meant for this plugin
        if not match:
            return False

        zoom = match.group(1)
        image_size = match.group(2, 3)

        try:
            zoom = int(zoom)
        except (ValueError, TypeError):
            zoom = self.config["zoom"] if "zoom" in self.config else None

        if zoom is not None and (zoom < 0 or zoom > 30):
            zoom = None

        try:
            image_size = (int(image_size[0]), int(image_size[1]))
        except (ValueError, TypeError):
            image_size = (
                self.config["image_width"] if "image_width" in self.config else 1000,
                self.config["image_height"] if "image_height" in self.config else 1000,
            )

        if image_size[0] > 1000 or image_size[1] > 1000:
            image_size = (1000, 1000)

        locations = []
        for _node, info in meshtastic_client.nodes.items():
            if "position" in info and "latitude" in info["position"]:
                locations.append(
                    {
                        "lat": info["position"]["latitude"],
                        "lon": info["position"]["longitude"],
                        "label": info["user"]["shortName"],
                    }
                )

        if not locations:
            await matrix_client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "No nodes with valid positions found.",
                },
            )
            return True

        anonymize = self.config["anonymize"] if "anonymize" in self.config else True
        radius = self.config["radius"] if "radius" in self.config else 1000

        logger.debug(
            f"Generating map with zoom={zoom}, image_size={image_size}, anonymize={anonymize}, radius={radius}"
        )

        pillow_image = get_map(
            locations=locations,
            zoom=zoom,
            image_size=image_size,
            anonymize=anonymize,
            radius=radius,
        )

        await send_image(matrix_client, room.room_id, pillow_image)

        return True
