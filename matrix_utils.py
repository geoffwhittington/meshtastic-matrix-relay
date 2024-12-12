import asyncio
import io
import re
import ssl
import time
from typing import List, Union

import certifi
import meshtastic.protobuf.portnums_pb2
from nio import (
    AsyncClient,
    AsyncClientConfig,
    MatrixRoom,
    RoomMessageNotice,
    RoomMessageText,
    RoomMessageEmote,
    UploadResponse,
    WhoamiError,
    ReactionEvent,
)

from PIL import Image

from config import relay_config
from log_utils import get_logger

# Do not import plugin_loader here to avoid circular imports
from meshtastic_utils import connect_meshtastic
from db_utils import get_message_map_by_matrix_event_id

# Extract Matrix configuration
matrix_homeserver = relay_config["matrix"]["homeserver"]
matrix_rooms: List[dict] = relay_config["matrix_rooms"]
matrix_access_token = relay_config["matrix"]["access_token"]

bot_user_id = relay_config["matrix"]["bot_user_id"]
bot_user_name = None  # Detected upon logon
bot_start_time = int(
    time.time() * 1000
)  # Timestamp when the bot starts, used to filter out old messages

logger = get_logger(name="Matrix")

matrix_client = None

def bot_command(command, payload):
    # Checks if the given command is directed at the bot
    return f"{bot_user_name}: !{command}" in payload

async def connect_matrix():
    """
    Establish a connection to the Matrix homeserver.
    Sets global matrix_client and detects the bot's display name.
    """
    global matrix_client
    global bot_user_name
    if matrix_client:
        return matrix_client

    # Create SSL context using certifi's certificates
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # Initialize the Matrix client with custom SSL context
    config = AsyncClientConfig(encryption_enabled=False)
    matrix_client = AsyncClient(
        homeserver=matrix_homeserver,
        user=bot_user_id,
        config=config,
        ssl=ssl_context,
    )

    # Set the access_token and user_id
    matrix_client.access_token = matrix_access_token
    matrix_client.user_id = bot_user_id

    # Attempt to retrieve the device_id using whoami()
    whoami_response = await matrix_client.whoami()
    if isinstance(whoami_response, WhoamiError):
        logger.error(f"Failed to retrieve device_id: {whoami_response.message}")
        matrix_client.device_id = None
    else:
        matrix_client.device_id = whoami_response.device_id
        if matrix_client.device_id:
            logger.debug(f"Retrieved device_id: {matrix_client.device_id}")
        else:
            logger.warning("device_id not returned by whoami()")

    # Fetch the bot's display name
    response = await matrix_client.get_displayname(bot_user_id)
    if hasattr(response, "displayname"):
        bot_user_name = response.displayname
    else:
        bot_user_name = bot_user_id  # Fallback if display name is not set

    return matrix_client

async def join_matrix_room(matrix_client, room_id_or_alias: str) -> None:
    """Join a Matrix room by its ID or alias."""
    try:
        if room_id_or_alias.startswith("#"):
            # If it's a room alias, resolve it to a room ID
            response = await matrix_client.room_resolve_alias(room_id_or_alias)
            if not response.room_id:
                logger.error(
                    f"Failed to resolve room alias '{room_id_or_alias}': {response.message}"
                )
                return
            room_id = response.room_id
            # Update the room ID in the matrix_rooms list
            for room_config in matrix_rooms:
                if room_config["id"] == room_id_or_alias:
                    room_config["id"] = room_id
                    break
        else:
            room_id = room_id_or_alias

        # Attempt to join the room if not already joined
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

async def matrix_relay(room_id, message, longname, shortname, meshnet_name, portnum, meshtastic_id=None, meshtastic_replyId=None, meshtastic_text=None, emote=False, emoji=False):
    """
    Relay a message from Meshtastic to Matrix, optionally storing message maps.

    :param room_id: The Matrix room ID to send to.
    :param message: The text message to send.
    :param longname: The sender's longname on the meshnet.
    :param shortname: The sender's shortname on the meshnet.
    :param meshnet_name: The meshnet name passed in, but we will always override with our own relay's meshnet_name.
    :param portnum: The portnum or message type source from Meshtastic.
    :param meshtastic_id: The Meshtastic ID of the message, if any.
    :param meshtastic_replyId: The Meshtastic replyId if this is a reaction.
    :param meshtastic_text: The original Meshtastic text message if available.
    :param emote: If True, send as an emote instead of a normal message.
    :param emoji: If True, indicates this was originally a reaction.
    """
    matrix_client = await connect_matrix()
    try:
        # Always use our own local meshnet_name for outgoing events
        local_meshnet_name = relay_config["meshtastic"]["meshnet_name"]
        content = {
            "msgtype": "m.text" if not emote else "m.emote",
            "body": message,
            "meshtastic_longname": longname,
            "meshtastic_shortname": shortname,
            "meshtastic_meshnet": local_meshnet_name,
            "meshtastic_portnum": portnum,
        }
        if meshtastic_id is not None:
            content["meshtastic_id"] = meshtastic_id
        if meshtastic_replyId is not None:
            content["meshtastic_replyId"] = meshtastic_replyId
        if meshtastic_text is not None:
            content["meshtastic_text"] = meshtastic_text
        if emoji:
            content["meshtastic_emoji"] = 1

        response = await asyncio.wait_for(
            matrix_client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
            ),
            timeout=5.0,
        )
        logger.info(f"Sent inbound radio message to matrix room: {room_id}")

        # For inbound meshtastic->matrix messages, store mapping here if meshtastic_id is present and not a reaction
        if meshtastic_id is not None and not emote:
            from db_utils import store_message_map
            # Always store our own local meshnet_name to identify origin
            store_message_map(meshtastic_id, response.event_id, room_id, meshtastic_text if meshtastic_text else message, meshtastic_meshnet=local_meshnet_name)

    except asyncio.TimeoutError:
        logger.error("Timed out while waiting for Matrix response")
    except Exception as e:
        logger.error(f"Error sending radio message to matrix room {room_id}: {e}")

def truncate_message(
    text, max_bytes=227
):
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
    room: MatrixRoom, event: Union[RoomMessageText, RoomMessageNotice, ReactionEvent, RoomMessageEmote]
) -> None:
    """
    Handle new messages and reactions in Matrix. For reactions, we ensure that when relaying back
    to Meshtastic, we always apply our local meshnet_name to outgoing events.
    """
    from db_utils import store_message_map
    full_display_name = "Unknown user"
    message_timestamp = event.server_timestamp

    # We do not relay messages that occurred before the bot started
    if message_timestamp < bot_start_time:
        return

    # Find the room_config that matches this room, if any
    room_config = None
    for config in matrix_rooms:
        if config["id"] == room.room_id:
            room_config = config
            break

    # Only proceed if the room is supported
    if not room_config:
        return

    relates_to = event.source["content"].get("m.relates_to")
    is_reaction = False
    reaction_emoji = None
    original_matrix_event_id = None

    # Check if this is a Matrix ReactionEvent (usually m.reaction)
    if isinstance(event, ReactionEvent):
        # This is a reaction event
        is_reaction = True
        logger.debug(f"Processing Matrix reaction event: {event.source}")
        if relates_to and "event_id" in relates_to and "key" in relates_to:
            # Extract the reaction emoji and the original event it relates to
            reaction_emoji = relates_to["key"]
            original_matrix_event_id = relates_to["event_id"]
            logger.debug(f"Original matrix event ID: {original_matrix_event_id}, Reaction emoji: {reaction_emoji}")

    # Check if this is a Matrix RoomMessageEmote (m.emote)
    if isinstance(event, RoomMessageEmote):
        logger.debug(f"Processing Matrix reaction event: {event.source}")
        is_reaction = True
        # We need to manually extract the reaction emoji from the body
        reaction_body = event.source["content"].get("body", "")
        reaction_match = re.search(r"reacted (.+?) to", reaction_body)
        reaction_emoji = reaction_match.group(1).strip() if reaction_match else "?"

    text = event.body.strip() if (not is_reaction and hasattr(event, "body")) else ""

    longname = event.source["content"].get("meshtastic_longname")
    shortname = event.source["content"].get("meshtastic_shortname", None)
    meshnet_name = event.source["content"].get("meshtastic_meshnet")
    meshtastic_replyId = event.source["content"].get("meshtastic_replyId")
    suppress = event.source["content"].get("mmrelay_suppress")

    # Retrieve the relay_reactions option from config
    relay_reactions = relay_config["meshtastic"].get("relay_reactions", True)

    # If a message has suppress flag, do not process
    if suppress:
        return

    local_meshnet_name = relay_config["meshtastic"]["meshnet_name"]

    # Handle ReactionEvent (local reaction)
    if isinstance(event, ReactionEvent) and relay_reactions:
        if original_matrix_event_id:
            orig = get_message_map_by_matrix_event_id(original_matrix_event_id)
            if orig:
                # orig = (meshtastic_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
                meshtastic_id, matrix_room_id, meshtastic_text_db, meshtastic_meshnet_db = orig
                display_name_response = await matrix_client.get_displayname(event.sender)
                full_display_name = display_name_response.displayname or event.sender

                # If not from a remote meshnet, proceed as normal to relay back to the originating meshnet
                short_display_name = full_display_name[:5]
                prefix = f"{short_display_name}[M]: "
                abbreviated_text = meshtastic_text_db[:40] + "..." if len(meshtastic_text_db) > 40 else meshtastic_text_db

                # Always use our local meshnet_name for outgoing events
                
                reaction_message = f"{prefix}reacted {reaction_emoji} to \"{abbreviated_text}\""
                meshtastic_interface = connect_meshtastic()
                from meshtastic_utils import logger as meshtastic_logger
                meshtastic_channel = room_config["meshtastic_channel"]

                if relay_config["meshtastic"]["broadcast_enabled"]:
                    meshtastic_logger.info(
                        f"Relaying reaction from {full_display_name} to radio broadcast"
                    )
                    logger.debug(f"Sending reaction to Meshtastic with meshnet={local_meshnet_name}: {reaction_message}")
                    meshtastic_interface.sendText(
                        text=reaction_message, channelIndex=meshtastic_channel
                    )
                return

    # Handle remote reaction (RoomMessageEmote)
    if isinstance(event, RoomMessageEmote) and relay_reactions:
        # Check if we need to relay a reaction from a remote meshnet to our local meshnet.
        # Correctly identify remote reactions by checking for presence of 'meshtastic_replyId'
        # and that it is an emote, and that the meshnet_name is not our own.
        if meshnet_name and meshnet_name != local_meshnet_name and meshtastic_replyId:
            logger.info(f"Relaying reaction from remote meshnet: {meshnet_name}")
            # Always use our local meshnet_name for outgoing events

            short_meshnet_name = local_meshnet_name[:4]

            # Format the reaction message for relaying to the local meshnet.
            # Use the shortname and emoji extracted from the m.emote event
            if not shortname:
                shortname = longname[:3] if longname else "???"

            reaction_message = f"{shortname}/{short_meshnet_name} reacted {reaction_emoji} to \"{text[:40]}{'...' if len(text) > 40 else ''}\""

            # Relay the remote reaction to the local meshnet.
            meshtastic_interface = connect_meshtastic()
            from meshtastic_utils import logger as meshtastic_logger
            meshtastic_channel = room_config["meshtastic_channel"]

            if relay_config["meshtastic"]["broadcast_enabled"]:
                meshtastic_logger.info(
                    f"Relaying reaction from remote meshnet {meshnet_name} to radio broadcast"
                )
                logger.debug(f"Sending reaction to Meshtastic with meshnet={local_meshnet_name}: {reaction_message}")
                meshtastic_interface.sendText(
                    text=reaction_message, channelIndex=meshtastic_channel
                )

            # We've relayed the remote reaction to our local mesh, so we're done.
            return

    # For Matrix->Mesh messages from a remote meshnet, rewrite the message format
    if longname and meshnet_name:
        # Always include the meshnet_name in the full display name.
        full_display_name = f"{longname}/{meshnet_name}"

        if meshnet_name != local_meshnet_name:
            # A message from a remote meshnet relayed into Matrix, now going back out
            logger.info(f"Processing message from remote meshnet: {meshnet_name}")
            short_meshnet_name = meshnet_name[:4]
            # If shortname is not available, derive it from the longname
            if shortname is None:
                shortname = longname[:3] if longname else "???"
            # Remove the original prefix "[longname/meshnet]: " to avoid double-tagging
            text = re.sub(
                rf"^\[{full_display_name}\]: ", "", text
            )
            text = truncate_message(text)
            full_message = f"{shortname}/{short_meshnet_name}: {text}"
        else:
            # If this message is from our local meshnet (loopback), we ignore it
            return
    else:
        # Normal Matrix message from a Matrix user
        display_name_response = await matrix_client.get_displayname(event.sender)
        full_display_name = display_name_response.displayname or event.sender
        short_display_name = full_display_name[:5]
        prefix = f"{short_display_name}[M]: "
        logger.debug(f"Processing matrix message from [{full_display_name}]: {text}")
        full_message = f"{prefix}{text}"
        text = truncate_message(text)

    # Plugin functionality
    from plugin_loader import load_plugins
    plugins = load_plugins()

    found_matching_plugin = False
    for plugin in plugins:
        if not found_matching_plugin:
            found_matching_plugin = await plugin.handle_room_message(
                room, event, full_message
            )
            if found_matching_plugin:
                logger.debug(f"Processed by plugin {plugin.plugin_name}")

    # Check if the message is a command directed at the bot
    is_command = False
    for plugin in plugins:
        for command in plugin.get_matrix_commands():
            if bot_command(command, text):
                is_command = True
                break
        if is_command:
            break

    # If this is a command, we do not send it to the mesh
    if is_command:
        logger.debug("Message is a command, not sending to mesh")
        return

    # Connect to Meshtastic
    meshtastic_interface = connect_meshtastic()
    from meshtastic_utils import logger as meshtastic_logger

    meshtastic_channel = room_config["meshtastic_channel"]

    # If message is from Matrix and broadcast_enabled is True, relay to Meshtastic
    if not found_matching_plugin and event.sender != bot_user_id:
        if relay_config["meshtastic"]["broadcast_enabled"]:
            portnum = event.source["content"].get("meshtastic_portnum")
            if (
                portnum == "DETECTION_SENSOR_APP"
            ):
                # If detection_sensor is enabled, forward this data as detection sensor data
                if relay_config["meshtastic"].get("detection_sensor", False):
                    sent_packet = meshtastic_interface.sendData(
                        data=full_message.encode("utf-8"),
                        channelIndex=meshtastic_channel,
                        portNum=meshtastic.protobuf.portnums_pb2.PortNum.DETECTION_SENSOR_APP,
                    )
                    # If we got a packet with an id and it's not a reaction, store mapping
                    if sent_packet and hasattr(sent_packet, 'id'):
                        store_message_map(sent_packet.id, event.event_id, room.room_id, text, meshtastic_meshnet=local_meshnet_name)
                else:
                    meshtastic_logger.debug(
                        f"Detection sensor packet received from {full_display_name}, but detection sensor processing is disabled."
                    )
            else:
                meshtastic_logger.info(
                    f"Relaying message from {full_display_name} to radio broadcast"
                )
                sent_packet = meshtastic_interface.sendText(
                    text=full_message, channelIndex=meshtastic_channel
                )
                if sent_packet and hasattr(sent_packet, 'id'):
                    store_message_map(sent_packet.id, event.event_id, room.room_id, text, meshtastic_meshnet=local_meshnet_name)
        else:
            logger.debug(
                f"Broadcast not supported: Message from {full_display_name} dropped."
            )

async def upload_image(
    client: AsyncClient, image: Image.Image, filename: str
) -> UploadResponse:
    """
    Uploads an image to Matrix and returns the UploadResponse containing the content URI.
    """
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
    """
    Sends an already uploaded image to the specified room.
    """
    await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={"msgtype": "m.image", "url": upload_response.content_uri, "body": ""},
    )
