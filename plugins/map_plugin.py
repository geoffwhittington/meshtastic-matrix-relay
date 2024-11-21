import staticmaps
import s2sphere
import math
import random
import io
import re
from PIL import Image, ImageDraw, ImageFont
from nio import AsyncClient, UploadResponse
from plugins.base_plugin import BasePlugin
import os


class TextLabel(staticmaps.Object):
    def __init__(self, latlng: s2sphere.LatLng, text: str, fontSize: int = 12) -> None:
        staticmaps.Object.__init__(self)
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

        # Attempt to load a font that supports emojis
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",  # Common on Linux
            "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoEmoji-Bold.ttf",
            "/System/Library/Fonts/Apple Color Emoji.ttf",  # macOS
            "C:\\Windows\\Fonts\\seguiemj.ttf",  # Windows Segoe UI Emoji
        ]

        font = None
        for path in font_paths:
            if os.path.isfile(path):
                try:
                    font = ImageFont.truetype(path, self._font_size)
                    break
                except Exception as e:
                    pass

        if not font:
            # If emoji font not found, use default font
            font = ImageFont.load_default()
            self._text = self._text.encode('ascii', 'ignore').decode('ascii')  # Remove non-ASCII characters

        # Get the size of the text using textsize or textbbox
        try:
            bbox = renderer.draw().textbbox((0, 0), self._text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception as e:
            # Fallback in case of an error
            tw, th = renderer.draw().textsize(self._text, font=font)

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
            font=font,
        )

    def render_cairo(self, renderer: staticmaps.CairoRenderer) -> None:
        # Since Cairo is not being used, we can leave this method empty
        pass

    def render_svg(self, renderer: staticmaps.SvgRenderer) -> None:
        x, y = renderer.transformer().ll2pixel(self.latlng())

        # Guess text extents
        tw = len(self._text) * self._font_size * 0.5
        th = self._font_size * 1.2

        w = max(self._arrow, tw + 2 * self._margin)
        h = th + 2 * self._margin

        path = renderer.drawing().path(
            fill="#ffffff",
            stroke="#ff0000",
            stroke_width=1,
            opacity=1.0,
        )
        path.push(f"M {x} {y}")
        path.push(f" l {self._arrow / 2} {-self._arrow}")
        path.push(f" l {w / 2 - self._arrow / 2} 0")
        path.push(f" l 0 {-h}")
        path.push(f" l {-w} 0")
        path.push(f" l 0 {h}")
        path.push(f" l {w / 2 - self._arrow / 2} 0")
        path.push("Z")
        renderer.group().add(path)

        renderer.group().add(
            renderer.drawing().text(
                self._text,
                text_anchor="middle",
                dominant_baseline="central",
                insert=(x, y - self._arrow - h / 2),
                font_family="sans-serif",
                font_size=f"{self._font_size}px",
                fill="#000000",
            )
        )


def anonymize_location(lat, lon, radius=1000):
    # Generate random offsets for latitude and longitude
    # Convert latitude to radians for math.cos()
    lat_rad = math.radians(lat)
    lat_offset = random.uniform(-radius / 111320, radius / 111320)
    lon_offset = random.uniform(
        -radius / (111320 * math.cos(lat_rad)), radius / (111320 * math.cos(lat_rad))
    )

    # Apply the offsets to the location coordinates
    new_lat = lat + lat_offset
    new_lon = lon + lon_offset

    return new_lat, new_lon


def get_map(locations, zoom=None, image_size=None, anonymize=True, radius=10000):
    """
    Anonymize a location to 10km by default
    """
    context = staticmaps.Context()
    context.set_tile_provider(staticmaps.tile_provider_OSM)
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

    # Render non-anti-aliased PNG
    if image_size:
        return context.render_pillow(image_size[0], image_size[1])
    else:
        return context.render_pillow(1000, 1000)


async def upload_image(client: AsyncClient, image: Image.Image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_data = buffer.getvalue()
    buffer.seek(0)  # Reset buffer to the beginning

    response, maybe_keys = await client.upload(
        buffer,
        content_type="image/png",
        filename="location.png",
        filesize=len(image_data),
    )

    # Get image dimensions
    width, height = image.size

    return response, len(image_data), width, height


async def send_room_image(
    client: AsyncClient,
    room_id: str,
    upload_response: UploadResponse,
    image_size: int,
    width: int,
    height: int,
):
    await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={
            "msgtype": "m.image",
            "body": "location.png",
            "url": upload_response.content_uri,
            "info": {
                "mimetype": "image/png",
                "size": image_size,
                "w": width,
                "h": height,
            },
        },
    )


async def send_image(client: AsyncClient, room_id: str, image: Image.Image):
    response, image_size, width, height = await upload_image(client=client, image=image)
    await send_room_image(
        client,
        room_id,
        upload_response=response,
        image_size=image_size,
        width=width,
        height=height,
    )


class Plugin(BasePlugin):
    plugin_name = "map"

    @property
    def description(self):
        return (
            f"Map of mesh radio nodes. Supports `zoom` and `size` options to customize"
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
        except:
            zoom = self.config.get("zoom", 13)

        if zoom < 0 or zoom > 30:
            zoom = 8

        try:
            image_size = (int(image_size[0]), int(image_size[1]))
        except:
            image_size = (
                self.config.get("image_width", 1000),
                self.config.get("image_height", 1000),
            )

        if image_size[0] > 1000 or image_size[1] > 1000:
            image_size = (1000, 1000)

        locations = []
        for node, info in meshtastic_client.nodes.items():
            if "position" in info and "latitude" in info["position"]:
                locations.append(
                    {
                        "lat": info["position"]["latitude"],
                        "lon": info["position"]["longitude"],
                        "label": info["user"]["shortName"],
                    }
                )

        if not locations:
            await self.send_matrix_message(room.room_id, "No node locations available.")
            return True

        anonymize = self.config.get("anonymize", True)
        radius = self.config.get("radius", 1000)

        pillow_image = get_map(
            locations=locations,
            zoom=zoom,
            image_size=image_size,
            anonymize=anonymize,
            radius=radius,
        )

        await send_image(matrix_client, room.room_id, pillow_image)

        return True
