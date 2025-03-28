import asyncio
import io
import os  # Import os for path joining
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
    ReactionEvent,
    RoomMessageEmote,
    RoomMessageNotice,
    RoomMessageText,
    UploadResponse,
    WhoamiError,
    exceptions as NioExceptions,
)
from nio.store import PeeweeStore, StoreError  # Import PeeweeStore and StoreError

from PIL import Image

from config import get_app_path, relay_config  # Import get_app_path
from db_utils import (
    get_message_map_by_matrix_event_id,
    prune_message_map,
    store_message_map,
)
from log_utils import get_logger

# Do not import plugin_loader here to avoid circular imports
from meshtastic_utils import connect_meshtastic

# Extract Matrix configuration
matrix_homeserver = relay_config["matrix"]["homeserver"]
matrix_rooms: List[dict] = relay_config["matrix_rooms"]
matrix_access_token = relay_config["matrix"]["access_token"]
matrix_encryption_config = relay_config["matrix"].get("encryption", {})

bot_user_id = relay_config["matrix"]["bot_user_id"]
bot_user_name = None  # Detected upon logon
bot_start_time = int(
    time.time() * 1000
)  # Timestamp when the bot starts, used to filter out old messages

logger = get_logger(name="Matrix")

matrix_client = None


def bot_command(command, event):
    """
    Checks if the given command is directed at the bot,
    accounting for variations in different Matrix clients.
    """
    full_message = event.body.strip()
    content = event.source.get("content", {})
    formatted_body = content.get("formatted_body", "")

    # Remove HTML tags and extract the text content
    text_content = re.sub(r"<[^>]+>", "", formatted_body).strip()

    # Check if the message starts with bot_user_id or bot_user_name
    if full_message.startswith(bot_user_id) or text_content.startswith(bot_user_id):
        # Construct a regex pattern to match variations of bot mention and command
        pattern = rf"^(?:{re.escape(bot_user_id)}|{re.escape(bot_user_name)}|[#@].+?)[,:;]?\s*!{command}"
        return bool(re.match(pattern, full_message)) or bool(
            re.match(pattern, text_content)
        )
    elif full_message.startswith(bot_user_name) or text_content.startswith(
        bot_user_name
    ):
        # Construct a regex pattern to match variations of bot mention and command
        pattern = rf"^(?:{re.escape(bot_user_id)}|{re.escape(bot_user_name)}|[#@].+?)[,:;]?\s*!{command}"
        return bool(re.match(pattern, full_message)) or bool(
            re.match(pattern, text_content)
        )
    else:
        return False


async def connect_matrix():
    """
    Establish a connection to the Matrix homeserver.
    Sets global matrix_client and detects the bot's display name.
    Handles E2EE setup if enabled in the configuration.
    """
    global matrix_client
    global bot_user_name
    if matrix_client:
        return matrix_client

    # --- E2EE Setup ---
    store = None
    encryption_enabled = matrix_encryption_config.get("enabled", False)
    if encryption_enabled:
        store_path = matrix_encryption_config.get("store_path", "matrix_store")
        passphrase = matrix_encryption_config.get("passphrase")
        # Ensure store_path is absolute or relative to the app path
        if not os.path.isabs(store_path):
            store_path = os.path.join(get_app_path(), store_path)

        os.makedirs(store_path, exist_ok=True) # Ensure the store directory exists
        logger.info(f"Encryption enabled. Using store path: {store_path}")
        if passphrase:
            logger.info("Using encryption store passphrase.")
        else:
            logger.warning(
                "Encryption store passphrase is NOT set. Keys will be stored unencrypted on disk."
            )

        try:
            store = PeeweeStore(
                bot_user_id,
                store_path,
                passphrase=passphrase if passphrase else None,
            )
        except StoreError as e:
            logger.error(f"Failed to initialize encryption store: {e}")
            logger.error("Ensure 'olm' library is installed (`pip install python-olm`) and dependencies are met.")
            logger.error("Disabling encryption due to store initialization failure.")
            encryption_enabled = False
        except Exception as e:
            logger.error(f"An unexpected error occurred during encryption store initialization: {e}")
            logger.error("Disabling encryption.")
            encryption_enabled = False

    # Create SSL context using certifi's certificates
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # Initialize the Matrix client config
    # store_sync_tokens is True by default. encryption_enabled is False by default.
    config = AsyncClientConfig(
        encryption_enabled=encryption_enabled,
        store_path=store_path if encryption_enabled else None, # Pass path for potential auto-creation if store=None
        store_sync_tokens=True, # Default, but explicit
    )

    # Initialize the Matrix client
    matrix_client = AsyncClient(
        homeserver=matrix_homeserver,
        user=bot_user_id,
        config=config,
        store=store, # Pass the store object if created
        ssl=ssl_context,
    )

    # Set the access_token and user_id (redundant but explicit)
    matrix_client.access_token = matrix_access_token
    matrix_client.user_id = bot_user_id

    # --- E2EE Post-Init ---
    if encryption_enabled and store:
        # Trust own device implicitly and ignore others (as requested)
        matrix_client.trust_devices(bot_user_id, TrustLevel.TRUSTED) # Trust own devices
        matrix_client.ignore_unverified_devices = True
        logger.info("E2EE: Ignoring unverified devices.")
        # Loading the store happens automatically during login/sync if store object is provided

    # Attempt to retrieve the device_id using whoami()
    # This also helps confirm the token is valid
    try:
        whoami_response = await matrix_client.whoami()
        if isinstance(whoami_response, WhoamiError):
            logger.error(f"Failed to verify token/user with whoami: {whoami_response.message}")
            # Decide if we should exit or try to continue
            # For now, let's try to continue, sync might fail later
            matrix_client.device_id = None
        else:
            matrix_client.device_id = whoami_response.device_id
            if matrix_client.device_id:
                logger.info(f"Logged in with user_id: {matrix_client.user_id}, device_id: {matrix_client.device_id}")
                # If E2EE is enabled, associate the store with this device ID implicitly
            else:
                logger.warning("device_id not returned by whoami()")

    except NioExceptions.UnknownTokenError:
        logger.error("Matrix login failed: Unknown or invalid access token.")
        logger.error("Please check your matrix.access_token in config.yaml.")
        return None # Cannot proceed without valid login
    except Exception as e:
        logger.error(f"An error occurred during Matrix whoami check: {e}")
        # Continue, but things might be broken
        matrix_client.device_id = None


    # Fetch the bot's display name
    try:
        response = await matrix_client.get_displayname(bot_user_id)
        if hasattr(response, "displayname") and response.displayname:
            bot_user_name = response.displayname
            logger.info(f"Detected bot display name: {bot_user_name}")
        else:
            bot_user_name = bot_user_id.split(":")[0][1:] # Extract localpart as fallback
            logger.info(f"Using fallback bot display name: {bot_user_name}")
    except Exception as e:
        logger.warning(f"Could not fetch bot display name: {e}")
        bot_user_name = bot_user_id.split(":")[0][1:] # Fallback
        logger.info(f"Using fallback bot display name: {bot_user_name}")


    return matrix_client


async def join_matrix_room(matrix_client, room_id_or_alias: str) -> None:
    """Join a Matrix room by its ID or alias."""
    try:
        if room_id_or_alias.startswith("#"):
            # If it's a room alias, resolve it to a room ID
            logger.debug(f"Resolving room alias '{room_id_or_alias}'...")
            response = await matrix_client.room_resolve_alias(room_id_or_alias)
            if not hasattr(response, 'room_id') or not response.room_id:
                logger.error(
                    f"Failed to resolve room alias '{room_id_or_alias}': {getattr(response, 'message', 'Unknown error')}"
                )
                return
            room_id = response.room_id
            logger.debug(f"Resolved '{room_id_or_alias}' to room ID '{room_id}'")
            # Update the room ID in the matrix_rooms list if necessary (can cause issues if called multiple times)
            # It's safer to assume the user provides correct IDs or handles aliases correctly
            # for room_config in matrix_rooms:
            #     if room_config["id"] == room_id_or_alias:
            #         room_config["id"] = room_id
            #         break
        else:
            room_id = room_id_or_alias

        # Attempt to join the room if not already joined
        if room_id not in matrix_client.rooms:
            logger.info(f"Attempting to join room '{room_id}'...")
            response = await matrix_client.join(room_id)
            # Check response type for join success
            if hasattr(response, 'room_id') and response.room_id == room_id:
                logger.info(f"Joined room '{room_id}' successfully")
            else:
                # Log specific error if available
                error_message = getattr(response, 'message', 'Unknown error during join')
                status_code = getattr(response, 'status_code', 'N/A')
                logger.error(f"Failed to join room '{room_id}': {error_message} (Status: {status_code})")
        else:
            logger.debug(f"Bot is already in room '{room_id}'")
            # Ensure we have keys for the room if it's encrypted
            if matrix_client.encryption_enabled and room_id in matrix_client.encrypted_rooms:
                 await matrix_client.sync(once=True, full_state=True) # Ensure keys are shared

    except Exception as e:
        logger.error(f"Error joining/processing room '{room_id_or_alias}': {e}")


async def matrix_relay(
    room_id,
    message,
    longname,
    shortname,
    meshnet_name,
    portnum,
    meshtastic_id=None,
    meshtastic_replyId=None,
    meshtastic_text=None,
    emote=False,
    emoji=False,
):
    """
    Relay a message from Meshtastic to Matrix, optionally storing message maps.
    Ensures custom fields are placed within the 'content' dictionary for E2EE compatibility.

    IMPORTANT CHANGE: Now, we only store message maps if `relay_reactions` is True.
    If `relay_reactions` is False, we skip storing to the message map entirely.
    This helps maintain privacy and prevents message_map usage unless needed.

    Additionally, if `msgs_to_keep` > 0, we prune the oldest messages after storing
    to prevent database bloat and maintain privacy.
    """
    matrix_client = await connect_matrix()
    if not matrix_client:
        logger.error("Matrix client not available, cannot relay message.")
        return

    # Retrieve relay_reactions configuration; default to False now if not specified.
    relay_reactions = relay_config["meshtastic"].get("relay_reactions", False)

    # Retrieve db config for message_map pruning
    db_config = relay_config.get("db", {})
    msg_map_config = db_config.get("msg_map", {})
    msgs_to_keep = msg_map_config.get(
        "msgs_to_keep", 500
    )  # Default is 500 if not specified

    try:
        # Always use our own local meshnet_name for outgoing events
        local_meshnet_name = relay_config["meshtastic"]["meshnet_name"]

        # *** E2EE Change: Move ALL custom fields INSIDE content ***
        content = {
            "msgtype": "m.emote" if emote else "m.text",
            "body": message,
            # Custom fields go here:
            "dev.meshtastic.relay": { # Namespaced custom data
                "longname": longname,
                "shortname": shortname,
                "meshnet": local_meshnet_name, # Use local name for outgoing context
                "portnum": str(portnum), # Ensure portnum is string if needed
                "id": meshtastic_id,
                "replyId": meshtastic_replyId,
                "text": meshtastic_text,
                "is_emoji_reaction": emoji,
            }
        }
        # Remove None values from custom data to keep payload clean
        content["dev.meshtastic.relay"] = {k: v for k, v in content["dev.meshtastic.relay"].items() if v is not None}

        logger.debug(f"Sending message to Matrix room {room_id}. Encrypted: {room_id in matrix_client.encrypted_rooms if matrix_client else False}")
        response = await asyncio.wait_for(
            matrix_client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
            ),
            timeout=15.0, # Increased timeout slightly for potentially slower E2EE operations
        )

        # Check response type for success
        if isinstance(response, NioExceptions.RoomSendError):
             logger.error(f"Failed to send message to Matrix room {room_id}: {response.message} (Status: {response.status_code})")
             return # Don't proceed if sending failed

        event_id = getattr(response, 'event_id', None)
        if not event_id:
            logger.warning(f"Sent message to Matrix room {room_id}, but event_id was not returned in response.")
            return # Cannot store map without event_id

        logger.info(f"Sent inbound radio message to matrix room: {room_id} (Event ID: {event_id})")

        # Only store message map if relay_reactions is True and meshtastic_id is present and not an emote.
        # If relay_reactions is False, we skip storing entirely.
        if relay_reactions and meshtastic_id is not None and not emote:
            # Store the message map
            store_message_map(
                meshtastic_id,
                event_id, # Use the obtained event_id
                room_id,
                meshtastic_text if meshtastic_text else message, # Use original text if available
                meshtastic_meshnet=local_meshnet_name, # Store local meshnet context
            )

            # If msgs_to_keep > 0, prune old messages after inserting a new one
            if msgs_to_keep > 0:
                prune_message_map(msgs_to_keep)

    except asyncio.TimeoutError:
        logger.error(f"Timed out while sending message to Matrix room {room_id}")
    except NioExceptions.EncryptionError as e:
        logger.error(f"Matrix Encryption Error sending to room {room_id}: {e}")
    except Exception as e:
        logger.error(f"Error sending radio message to matrix room {room_id}: {e}")


def truncate_message(text, max_bytes=227):
    """
    Truncate the given text to fit within the specified byte size.

    :param text: The text to truncate.
    :param max_bytes: The maximum allowed byte size for the truncated text.
    :return: The truncated text.
    """
    if not isinstance(text, str): # Ensure input is a string
        text = str(text)
    truncated_text = text.encode("utf-8")[:max_bytes].decode("utf-8", "ignore")
    return truncated_text


def strip_quoted_lines(text: str) -> str:
    """
    Remove lines that begin with '>' to avoid including
    the original quoted part of a Matrix reply in reaction text.
    """
    lines = text.splitlines()
    filtered = [line for line in lines if not line.strip().startswith(">")]
    return " ".join(filtered).strip()


# Callback for new messages in Matrix room
async def on_room_message(
    room: MatrixRoom,
    event: Union[RoomMessageText, RoomMessageNotice, ReactionEvent, RoomMessageEmote],
) -> None:
    """
    Handle new messages and reactions in Matrix. For reactions, we ensure that when relaying back
    to Meshtastic, we always apply our local meshnet_name to outgoing events. E2EE messages
    should be decrypted transparently by nio before this callback is invoked.

    We must be careful not to relay reactions to reactions (reaction-chains),
    especially remote reactions that got relayed into the room as m.emote events,
    as we do not store them in the database. If we can't find the original message in the DB,
    it likely means it's a reaction to a reaction, and we stop there.

    Additionally, we only deal with message_map storage (and thus reaction linking)
    if relay_reactions is True. If it's False, none of these mappings are stored or used.

    Custom fields are expected inside `event.source['content']['dev.meshtastic.relay']`.
    """
    matrix_client = await connect_matrix() # Ensure client is available
    if not matrix_client:
        logger.warning("Matrix client not available in on_room_message.")
        return

    # Check if the message was decrypted (E2EE)
    was_encrypted = getattr(event, 'is_encrypted', False)
    decryption_error = getattr(event, 'decryption_error', None)

    if was_encrypted:
        logger.debug(f"Received encrypted message in room {room.room_id}. Event ID: {event.event_id}")
        if decryption_error:
            logger.error(f"Failed to decrypt message {event.event_id} in room {room.room_id}: {decryption_error}")
            # Optionally try to get sender info if available even without body
            sender_display_name = room.user_name(event.sender) or event.sender
            logger.warning(f"Cannot process undecryptable message from {sender_display_name}.")
            return # Cannot process if decryption failed

    # We do not relay messages that occurred before the bot started
    message_timestamp = event.server_timestamp
    if message_timestamp < bot_start_time:
        logger.debug(f"Ignoring old message {event.event_id} from {event.sender} (timestamp {message_timestamp} < {bot_start_time})")
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

    # --- Extract data from event ---
    content = event.source.get("content", {})
    relates_to = content.get("m.relates_to")
    # Custom data is now nested
    custom_data = content.get("dev.meshtastic.relay", {})

    is_reaction = False
    reaction_emoji = None
    original_matrix_event_id = None

    # Retrieve relay_reactions option from config, now defaulting to False
    relay_reactions = relay_config["meshtastic"].get("relay_reactions", False)

    # Check if this is a Matrix ReactionEvent (m.reaction)
    if isinstance(event, ReactionEvent) or (relates_to and relates_to.get("rel_type") == "m.annotation"):
        is_reaction = True
        logger.debug(f"Processing Matrix reaction event: {event.event_id}")
        if relates_to and "event_id" in relates_to and "key" in relates_to:
            reaction_emoji = relates_to["key"]
            original_matrix_event_id = relates_to["event_id"]
            logger.debug(
                f"Original matrix event ID: {original_matrix_event_id}, Reaction emoji: {reaction_emoji}"
            )
        else:
            logger.warning(f"Reaction event {event.event_id} missing relation info.")
            return # Cannot process reaction without relation

    # Check if this is a Matrix RoomMessageEmote possibly representing a relayed reaction
    # These have custom data indicating they are emoji reactions
    elif isinstance(event, RoomMessageEmote) and custom_data.get("is_emoji_reaction", False):
        is_reaction = True
        logger.debug(f"Processing Matrix emote likely representing a relayed reaction: {event.event_id}")
        # Extract original ID and emoji from custom data or body as fallback
        original_matrix_event_id = custom_data.get("replyId") # Check our custom field first
        reaction_body = content.get("body", "")
        reaction_match = re.search(r"reacted (.+?) to", reaction_body)
        reaction_emoji = reaction_match.group(1).strip() if reaction_match else custom_data.get("text") # Fallback to text if emoji pattern fails

        if not original_matrix_event_id or not reaction_emoji:
             logger.warning(f"Could not determine original event or emoji for relayed reaction emote {event.event_id}")
             return # Cannot process

        logger.debug(
            f"Original matrix event ID (from emote): {original_matrix_event_id}, Reaction emoji: {reaction_emoji}"
        )

    # Get the main text body if it's not primarily a reaction
    # Ensure event.body exists and is a string before stripping
    text = ""
    if not is_reaction and hasattr(event, 'body') and isinstance(event.body, str):
        text = event.body.strip()
    elif not is_reaction:
        logger.warning(f"Received non-reaction message {event.event_id} without a valid body.")
        # Maybe it's an image or other non-text message? Decide how to handle.
        # For now, we'll ignore messages without text unless they are reactions.
        return


    # Extract custom fields (now nested)
    longname = custom_data.get("longname")
    shortname = custom_data.get("shortname")
    meshnet_name = custom_data.get("meshnet")
    meshtastic_replyId = custom_data.get("replyId") # Used for remote reaction relay identification
    portnum = custom_data.get("portnum") # Retrieve portnum if present

    # If a message has suppress flag (if we were to add one), do not process
    # suppress = custom_data.get("mmrelay_suppress")
    # if suppress:
    #     return

    # --- Reaction Handling ---
    # If this is a reaction and relay_reactions is False, do nothing
    if is_reaction and not relay_reactions:
        logger.debug(
            "Reaction event encountered but relay_reactions is disabled. Doing nothing."
        )
        return

    local_meshnet_name = relay_config["meshtastic"]["meshnet_name"]

    # If this is a reaction and relay_reactions is True, attempt to relay it
    if is_reaction and relay_reactions:
        # Check if we need to relay a reaction from a remote meshnet to our local meshnet.
        # Identify remote reactions by checking if meshnet_name is present, different from local,
        # and the event is an emote (how we currently relay mesh->matrix reactions).
        if (
            meshnet_name # Check if meshnet context exists
            and meshnet_name != local_meshnet_name
            and isinstance(event, RoomMessageEmote) # Check if it's the specific type we use for relaying
            and original_matrix_event_id # Ensure we know what it reacted to (from custom data)
        ):
            logger.info(f"Relaying reaction from remote meshnet '{meshnet_name}' back to local mesh")

            # Get sender display name for attribution
            sender_display_name = room.user_name(event.sender) or event.sender

            # Use the names provided in the custom data
            ln = longname if longname else sender_display_name # Fallback longname
            sn = shortname if shortname else ln[:3] # Fallback shortname
            short_meshnet_name = meshnet_name[:4]

            # Need the text of the original message this reacted to. Fetch from DB via original_matrix_event_id
            orig_map = get_message_map_by_matrix_event_id(original_matrix_event_id)
            if orig_map:
                 _, _, meshtastic_text_db, _ = orig_map # Unpack (meshtastic_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
                 meshtastic_text_db = strip_quoted_lines(meshtastic_text_db)
                 meshtastic_text_db = meshtastic_text_db.replace("\n", " ").replace("\r", " ")
                 abbreviated_text = (
                     meshtastic_text_db[:40] + "..."
                     if len(meshtastic_text_db) > 40
                     else meshtastic_text_db
                 )
            else:
                 abbreviated_text = "original message" # Fallback if DB lookup fails
                 logger.warning(f"Could not find original message {original_matrix_event_id} in DB for remote reaction relay.")


            # Format the reaction message for relaying to the local meshnet.
            reaction_message = f'{sn}/{short_meshnet_name} reacted {reaction_emoji} to "{abbreviated_text}"'
            reaction_message = truncate_message(reaction_message) # Ensure it fits mesh limits

            # Relay the remote reaction to the local meshnet.
            meshtastic_interface = connect_meshtastic()
            if not meshtastic_interface:
                 logger.error("Meshtastic connection unavailable, cannot relay remote reaction.")
                 return

            from meshtastic_utils import logger as meshtastic_logger # Avoid shadowing

            meshtastic_channel = room_config["meshtastic_channel"]

            if relay_config["meshtastic"]["broadcast_enabled"]:
                meshtastic_logger.info(
                    f"Relaying reaction from remote meshnet {meshnet_name} (user {sender_display_name}) to radio broadcast"
                )
                logger.debug(
                    f"Sending reaction to Meshtastic: {reaction_message}"
                )
                meshtastic_interface.sendText(
                    text=reaction_message, channelIndex=meshtastic_channel
                )
            # We've relayed the remote reaction to our local mesh, so we're done.
            return

        # --- Handle reactions from Matrix users OR local mesh users relayed to Matrix ---
        # If original_matrix_event_id is set, this is a reaction to some other matrix event
        elif original_matrix_event_id: # Use elif to avoid processing remote reactions twice
            orig = get_message_map_by_matrix_event_id(original_matrix_event_id)
            if not orig:
                # If we don't find the original message in the DB, we suspect it's a reaction-to-reaction scenario
                # OR the original message wasn't stored (e.g., relay_reactions was false then, or it was an emote).
                logger.debug(
                    f"Original message {original_matrix_event_id} for reaction not found in DB. Not forwarding reaction {event.event_id}."
                )
                return

            # orig = (meshtastic_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
            orig_meshtastic_id, _, meshtastic_text_db, orig_meshtastic_meshnet = orig

            # Only relay if the original message originated from a Meshtastic network
            # (We don't relay Matrix reactions to Matrix messages back to the mesh)
            if not orig_meshtastic_id or not orig_meshtastic_meshnet:
                logger.debug(f"Original message {original_matrix_event_id} was not from Meshtastic. Ignoring Matrix reaction {event.event_id}.")
                return

            # Get the display name of the user who reacted
            try:
                 display_name_response = await matrix_client.get_displayname(event.sender)
                 full_display_name = display_name_response.displayname or event.sender
            except Exception:
                 full_display_name = event.sender # Fallback

            # Format the reaction message for Meshtastic
            short_display_name = full_display_name[:5]
            prefix = f"{short_display_name}[M]: " # Indicate Matrix origin

            meshtastic_text_db = strip_quoted_lines(meshtastic_text_db)
            meshtastic_text_db = meshtastic_text_db.replace("\n", " ").replace("\r", " ")
            abbreviated_text = (
                meshtastic_text_db[:40] + "..."
                if len(meshtastic_text_db) > 40
                else meshtastic_text_db
            )

            reaction_message = (
                f'{prefix}reacted {reaction_emoji} to "{abbreviated_text}"'
            )
            reaction_message = truncate_message(reaction_message) # Ensure it fits

            meshtastic_interface = connect_meshtastic()
            if not meshtastic_interface:
                 logger.error("Meshtastic connection unavailable, cannot relay Matrix reaction.")
                 return

            from meshtastic_utils import logger as meshtastic_logger # Avoid shadowing

            meshtastic_channel = room_config["meshtastic_channel"]

            # Send reaction back to mesh ONLY if broadcast is enabled
            if relay_config["meshtastic"]["broadcast_enabled"]:
                meshtastic_logger.info(
                    f"Relaying reaction from Matrix user {full_display_name} to radio broadcast"
                )
                logger.debug(
                    f"Sending reaction to Meshtastic: {reaction_message}"
                )
                # Send as simple text message
                meshtastic_interface.sendText(
                    text=reaction_message, channelIndex=meshtastic_channel
                )
            return # Reaction handled

    # --- Regular Message Handling (Not a reaction processed above) ---

    # If sender is the bot itself, ignore unless specific conditions met (e.g. loopback test)
    if event.sender == bot_user_id:
         logger.debug(f"Ignoring message {event.event_id} from self ({bot_user_id}).")
         return # Usually ignore self-messages

    # Get sender display name
    try:
         display_name_response = await matrix_client.get_displayname(event.sender)
         full_display_name = display_name_response.displayname or event.sender
    except Exception:
         full_display_name = event.sender # Fallback


    # Check if the message came from a relayed Meshtastic user (has custom data)
    if longname and meshnet_name:
        # A message originally from Meshtastic, relayed into Matrix, potentially from another relay instance.

        # Always use the full name provided in the custom data for display/logging.
        full_display_name_source = f"{longname}/{meshnet_name}"
        logger.debug(f"Processing message {event.event_id} originally from {full_display_name_source} (via Matrix user {event.sender})")

        # If the message's meshnet source is NOT our local one, it means it came from a *different* relay
        # connected to a *different* mesh. We should relay it to *our* mesh.
        if meshnet_name != local_meshnet_name:
            logger.info(f"Relaying message from remote meshnet '{meshnet_name}' (user {longname}) to local mesh")
            short_meshnet_name = meshnet_name[:4]
            # Use shortname from custom data, fallback to longname part
            sn = shortname if shortname else (longname[:3] if longname else "???")

            # The 'text' variable already contains the body sent by the *other* relay.
            # We should format it to indicate its remote origin.
            # The body might already contain a prefix like "[User/RemoteMesh]: " - we add our own context.
            # Let's use a clear format: "SN/RMT: original text"
            # We need the *original* message text if possible, which might be in custom_data['text']
            original_meshtastic_text = custom_data.get("text", text) # Prefer original text if available
            original_meshtastic_text = truncate_message(original_meshtastic_text) # Truncate original text part

            full_message = f"{sn}/{short_meshnet_name}: {original_meshtastic_text}"
            # No further truncation here, full_message is formatted for mesh

        else:
            # The message originated from *our* local meshnet (loopback via Matrix). Ignore it.
            logger.debug(f"Ignoring loopback message {event.event_id} originally from local meshnet '{meshnet_name}' (user {longname}).")
            return
    else:
        # Normal Matrix message from a standard Matrix user (no Meshtastic custom data)
        logger.debug(f"Processing matrix message {event.event_id} from [{full_display_name}]: {text}")
        short_display_name = full_display_name[:5]
        prefix = f"{short_display_name}[M]: "
        # Truncate the user-typed text before adding prefix
        truncated_user_text = truncate_message(text)
        full_message = f"{prefix}{truncated_user_text}"
        # full_message is now ready, already truncated effectively

    # --- Plugin Handling ---
    from plugin_loader import load_plugins # Import here to avoid circular deps at top level
    plugins = load_plugins()

    found_matching_plugin = False
    # Ensure full_message is defined before passing to plugins
    if 'full_message' not in locals():
        full_message = text # Fallback, though should be set above

    for plugin in plugins:
        if not found_matching_plugin:
            # Plugins need access to the event and the potentially formatted message
            # Let plugins decide how to handle based on event type and content
            try:
                 handled = await plugin.handle_room_message(room, event, full_message)
                 if handled: # Plugin indicates it handled the message
                      found_matching_plugin = True
                      logger.debug(f"Message {event.event_id} processed by plugin {plugin.plugin_name}")
            except Exception as e:
                 logger.error(f"Error executing handle_room_message for plugin {plugin.plugin_name}: {e}")

    # Check if the message is a command directed at the bot AFTER general handling attempts
    is_command = False
    # Re-check bot commands using the raw event, not potentially modified message
    for plugin in plugins:
        for command in plugin.get_matrix_commands():
            if bot_command(command, event):
                is_command = True
                # Plugin should have handled it via handle_room_message if it was active
                logger.debug(f"Message {event.event_id} identified as command for plugin {plugin.plugin_name}")
                break
        if is_command:
            break

    # If this is a command handled by a plugin, we do not send it to the mesh
    if is_command or found_matching_plugin:
        logger.debug(f"Message {event.event_id} was handled by a plugin or is a command, not relaying to mesh.")
        return

    # --- Relay to Meshtastic ---
    meshtastic_interface = connect_meshtastic()
    if not meshtastic_interface:
        logger.error("Meshtastic connection unavailable, cannot relay Matrix message.")
        return

    from meshtastic_utils import logger as meshtastic_logger # Avoid shadowing

    meshtastic_channel = room_config["meshtastic_channel"]

    # If message is from Matrix (or remote mesh) and broadcast_enabled is True, relay to Meshtastic
    if relay_config["meshtastic"]["broadcast_enabled"]:
        # Check if it's a Detection Sensor message being relayed
        # Use the portnum extracted from custom data if available
        is_detection_sensor_msg = (portnum == "DETECTION_SENSOR_APP" or
                                    portnum == meshtastic.protobuf.portnums_pb2.PortNum.DETECTION_SENSOR_APP)

        if is_detection_sensor_msg:
            # If detection_sensor config is enabled, forward this data as detection sensor data
            if relay_config["meshtastic"].get("detection_sensor", False):
                 meshtastic_logger.info(f"Relaying detection sensor data from {full_display_name} to radio channel {meshtastic_channel}")
                 # Send the payload (full_message might include prefix, consider sending original text)
                 # Let's send the formatted 'full_message' for now for consistency
                 payload = full_message.encode("utf-8")
                 sent_packet = meshtastic_interface.sendData(
                     data=payload,
                     channelIndex=meshtastic_channel,
                     portNum=meshtastic.protobuf.portnums_pb2.PortNum.DETECTION_SENSOR_APP,
                 )
                 # Store message map if reactions are enabled (even for data packets)
                 if relay_reactions and sent_packet and hasattr(sent_packet, "id"):
                     # Use 'text' (original user text) for storage, not the prefixed 'full_message'
                     store_message_map(
                         sent_packet.id,
                         event.event_id,
                         room.room_id,
                         text, # Store original text
                         meshtastic_meshnet=local_meshnet_name,
                     )
                     db_config = relay_config.get("db", {})
                     msg_map_config = db_config.get("msg_map", {})
                     msgs_to_keep = msg_map_config.get("msgs_to_keep", 500)
                     if msgs_to_keep > 0:
                         prune_message_map(msgs_to_keep)
            else:
                 meshtastic_logger.debug(
                     f"Detection sensor packet received from {full_display_name}, but detection sensor processing is disabled. Dropping."
                 )
        else:
            # Regular text message relay
            meshtastic_logger.info(
                f"Relaying message from {full_display_name} to radio broadcast on channel {meshtastic_channel}"
            )
            # Send the already formatted and truncated 'full_message'
            sent_packet = meshtastic_interface.sendText(
                text=full_message, channelIndex=meshtastic_channel
            )
            # Store message_map only if relay_reactions is True
            if relay_reactions and sent_packet and hasattr(sent_packet, "id"):
                # Use 'text' (original user text) for storage
                store_message_map(
                    sent_packet.id,
                    event.event_id,
                    room.room_id,
                    text, # Store original text
                    meshtastic_meshnet=local_meshnet_name,
                )
                db_config = relay_config.get("db", {})
                msg_map_config = db_config.get("msg_map", {})
                msgs_to_keep = msg_map_config.get("msgs_to_keep", 500)
                if msgs_to_keep > 0:
                    prune_message_map(msgs_to_keep)
    else:
        logger.debug(
            f"Broadcast not enabled: Message from {full_display_name} dropped."
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

    try:
        response, maybe_keys = await client.upload(
            io.BytesIO(image_data),
            content_type="image/png",
            filename=filename,
            filesize=len(image_data),
        )

        if isinstance(response, UploadResponse):
            return response
        else:
            logger.error(f"Failed to upload image '{filename}': {response}")
            return None # Indicate failure

    except Exception as e:
        logger.error(f"Error during image upload '{filename}': {e}")
        return None


async def send_room_image(
    client: AsyncClient, room_id: str, upload_response: UploadResponse, filename: str = "image.png"
):
    """
    Sends an already uploaded image to the specified room.
    """
    if not upload_response or not upload_response.content_uri:
        logger.error(f"Cannot send image to room {room_id}, invalid upload response.")
        return

    try:
        await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                 "msgtype": "m.image",
                 "body": filename, # Use filename as body fallback
                 "url": upload_response.content_uri,
                 "info": { # Optional: add image info if available
                     #"mimetype": "image/png",
                     #"size": upload_response.filesize # Need filesize from upload
                 }
            },
        )
        logger.info(f"Sent image {filename} to room {room_id}")
    except Exception as e:
        logger.error(f"Error sending image {filename} to room {room_id}: {e}")
