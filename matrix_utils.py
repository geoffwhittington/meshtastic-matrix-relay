import asyncio
import certifi
import io
import re
import ssl
import time
from typing import List, Union
from nio import (
    AsyncClient,
    AsyncClientConfig,
    MatrixRoom,
    RoomMessageText,
    RoomMessageNotice,
    UploadResponse,
)
from PIL import Image

from config import relay_config
from log_utils import get_logger
from plugin_loader import load_plugins
from meshtastic_utils import connect_meshtastic

matrix_homeserver = relay_config["matrix"]["homeserver"]
bot_user_id = relay_config["matrix"]["bot_user_id"]
matrix_rooms: List[dict] = relay_config["matrix_rooms"]
matrix_access_token = relay_config["matrix"]["access_token"]

bot_user_id = relay_config["matrix"]["bot_user_id"]
bot_start_time = int(
    time.time() * 1000
)  # Timestamp when the bot starts, used to filter out old messages

logger = get_logger(name="Matrix")

matrix_client = None


async def connect_matrix():
    global matrix_client
    if matrix_client:
        return matrix_client

    # Create SSL context using certifi's certificates
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # Initialize the Matrix client with custom SSL context
    config = AsyncClientConfig(encryption_enabled=False)
    matrix_client = AsyncClient(
        matrix_homeserver, bot_user_id, config=config, ssl=ssl_context
    )
    matrix_client.access_token = matrix_access_token
    return matrix_client


async def join_matrix_room(matrix_client, room_id_or_alias: str) -> None:
    """Join a Matrix room by its ID or alias."""
    try:
        if room_id_or_alias.startswith("#"):
            response = await matrix_client.resolve_room_alias(room_id_or_alias)
            if not response.room_id:
                logger.error(
                    f"Failed to resolve room alias '{room_id_or_alias}': {response.message}"
                )
                return
            room_id = response.room_id
        else:
            room_id = room_id_or_alias

        if room_id not in matrix_client.rooms:
            response = await matrix_client.join(room_id)
            if response and hasattr(response, "room_id"):
                logger.info(f"Joined room '{room_id_or_alias}' successfully")
            else:
                logger.error(
                    f"Failed to join room '{room_id_or_alias}': {response.message}"
                )
        else:
            logger.debug(f"Bot is already in room '{room_id_or_alias}'")
    except Exception as e:
        logger.error(f"Error joining room '{room_id_or_alias}': {e}")



# Send message to the Matrix room
async def matrix_relay(room_id, message, longname, meshnet_name):
    matrix_client = await connect_matrix()
    try:
        content = {
            "msgtype": "m.text",
            "body": message,
            "meshtastic_longname": longname,
            "meshtastic_meshnet": meshnet_name,
        }
        await asyncio.wait_for(
            matrix_client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
            ),
            timeout=0.5,
        )
        logger.info(f"Sent inbound radio message to matrix room: {room_id}")

    except asyncio.TimeoutError:
        logger.error(f"Timed out while waiting for Matrix response")
    except Exception as e:
        logger.error(f"Error sending radio message to matrix room {room_id}: {e}")


def truncate_message(
    text, max_bytes=227
):  # 227 is the maximum that we can run without an error so far.  228 throws an error.
    """
    Truncate the given text to fit within the specified byte size.

    :param text: The text to truncate.
    :param max_bytes: The maximum allowed byte size for the truncated text.
    :return: The truncated text.
    """
    truncated_text = text.encode("utf-8")[:max_bytes].decode("utf-8", "ignore")
    return truncated_text


# Callback for new messages in Matrix room
async def on_room_message(
    room: MatrixRoom, event: Union[RoomMessageText, RoomMessageNotice]
) -> None:
    full_display_name = "Unknown user"

    if event.sender != bot_user_id:
        message_timestamp = event.server_timestamp

        if message_timestamp > bot_start_time:
            text = event.body.strip()

            longname = event.source["content"].get("meshtastic_longname")
            meshnet_name = event.source["content"].get("meshtastic_meshnet")
            local_meshnet_name = relay_config["meshtastic"]["meshnet_name"]

            if longname and meshnet_name:
                full_display_name = f"{longname}/{meshnet_name}"
                if meshnet_name != local_meshnet_name:
                    logger.info(f"Processing message from remote meshnet: {text}")
                    short_longname = longname[:3]
                    short_meshnet_name = meshnet_name[:4]
                    prefix = f"{short_longname}/{short_meshnet_name}: "
                    text = re.sub(
                        rf"^\[{full_display_name}\]: ", "", text
                    )  # Remove the original prefix from the text
                    text = truncate_message(text)
                    full_message = f"{prefix}{text}"
                else:
                    # This is a message from a local user, it should be ignored no log is needed
                    return

            else:
                display_name_response = await matrix_client.get_displayname(
                    event.sender
                )
                full_display_name = display_name_response.displayname or event.sender
                short_display_name = full_display_name[:5]
                prefix = f"{short_display_name}[M]: "
                logger.debug(
                    f"Processing matrix message from [{full_display_name}]: {text}"
                )
                text = truncate_message(text)
                full_message = f"{prefix}{text}"

            room_config = None
            for config in matrix_rooms:
                if config["id"] == room.room_id:
                    room_config = config
                    break

            # Plugin functionality
            plugins = load_plugins()
            meshtastic_interface = connect_meshtastic()
            from meshtastic_utils import logger as meshtastic_logger

            for plugin in plugins:
                await plugin.handle_room_message(room, event, full_message)

            if room_config:
                meshtastic_channel = room_config["meshtastic_channel"]

                if relay_config["meshtastic"]["broadcast_enabled"]:
                    meshtastic_logger.info(
                        f"Relaying message from {full_display_name} to radio broadcast"
                    )
                    meshtastic_interface.sendText(
                        text=full_message, channelIndex=meshtastic_channel
                    )

                else:
                    logger.debug(
                        f"Broadcast not supported: Message from {full_display_name} dropped."
                    )


async def upload_image(
    client: AsyncClient, image: Image.Image, filename: str
) -> UploadResponse:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_data = buffer.getvalue()

    response, maybe_keys = await client.upload(
        io.BytesIO(image_data),
        content_type="image/png",
        filename=filename,
        filesize=len(image_data),
    )

    return response


async def send_room_image(
    client: AsyncClient, room_id: str, upload_response: UploadResponse
):
    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={"msgtype": "m.image", "url": upload_response.content_uri, "body": ""},
    )
