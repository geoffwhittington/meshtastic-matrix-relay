import staticmaps
import math
import random
import re
from PIL import Image
from nio import AsyncClient
from base_plugin import BasePlugin


from matrix_utils import connect_matrix, upload_image, send_room_image
from meshtastic_utils import connect_meshtastic


def anonymize_location(lat, lon, radius=1000):
    # Generate random offsets for latitude and longitude
    lat_offset = random.uniform(-radius / 111320, radius / 111320)
    lon_offset = random.uniform(
        -radius / (111320 * math.cos(lat)), radius / (111320 * math.cos(lat))
    )

    # Apply the offsets to the location coordinates
    new_lat = lat + lat_offset
    new_lon = lon + lon_offset

    return new_lat, new_lon


def get_map(locations, zoom=None, image_size=None, minimum_radius=10000):
    """
    Anonymize a location to 10km by default
    """
    context = staticmaps.Context()
    context.set_tile_provider(staticmaps.tile_provider_OSM)
    context.set_zoom(zoom)

    for location in locations:
        new_location = anonymize_location(
            lat=float(location["lat"]),
            lon=float(location["lon"]),
            radius=minimum_radius,
        )
        radio = staticmaps.create_latlng(new_location[0], new_location[1])
        context.add_object(staticmaps.Marker(radio, size=10))

    # render non-anti-aliased png
    if image_size:
        return context.render_pillow(image_size[0], image_size[1])
    else:
        return context.render_pillow(1000, 1000)


async def send_image(client: AsyncClient, room_id: str, image: Image.Image):
    response = await upload_image(client=client, image=image)
    await send_room_image(client, room_id, upload_response=response)


class Plugin(BasePlugin):
    plugin_name = "map"

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        return

    async def handle_room_message(self, room, event, full_message):
        if not self.matrix_allowed(room):
            return

        minimum_radius = (
            self.config["minimum_radius"] if "minimum_radius" in self.config else 10000
        )
        matrix_client = await connect_matrix()
        meshtastic_client = connect_meshtastic()

        pattern = r"^.*:(?: !map(?: zoom=(\d+))?(?: size=(\d+),(\d+))?)?$"
        match = re.match(pattern, full_message)
        if match:
            zoom = match.group(1)
            image_size = match.group(2, 3)

            try:
                zoom = int(zoom)
            except:
                zoom = 8

            if zoom < 0 or zoom > 30:
                zoom = 8

            try:
                image_size = (int(image_size[0]), int(image_size[1]))
            except:
                image_size = (1000, 1000)

            if image_size[0] > 1000 or image_size[1] > 1000:
                image_size = (1000, 1000)

            locations = []
            for node, info in meshtastic_client.nodes.items():
                if "position" in info and "latitude" in info["position"]:
                    locations.append(
                        {
                            "lat": info["position"]["latitude"],
                            "lon": info["position"]["longitude"],
                        }
                    )

            pillow_image = get_map(
                locations=locations,
                zoom=zoom,
                image_size=image_size,
                minimum_radius=minimum_radius,
            )

            await send_image(
                client=matrix_client,
                room_id=room.room_id,
                image=pillow_image,
                filename="location.png",
            )
