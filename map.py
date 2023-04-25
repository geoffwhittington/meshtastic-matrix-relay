import staticmaps  # pip install py-staticmaps
import math
import random


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


def get_map(locations, zoom=None, image_size=None, radius=10000):
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
            radius=radius,
        )
        radio = staticmaps.create_latlng(new_location[0], new_location[1])
        context.add_object(staticmaps.Marker(radio, size=10))

    # render non-anti-aliased png
    if image_size:
        return context.render_pillow(image_size[0], image_size[1])
    else:
        return context.render_pillow(1000, 1000)
