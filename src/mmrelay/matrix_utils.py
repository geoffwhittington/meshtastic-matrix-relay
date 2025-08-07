import asyncio
import getpass
import io
import json
import os
import re
import ssl
import time
from typing import Union
from urllib.parse import urlparse

import certifi
import meshtastic.protobuf.portnums_pb2
from nio import (
    AsyncClient,
    AsyncClientConfig,
    MatrixRoom,
    MegolmEvent,
    ReactionEvent,
    RoomEncryptionEvent,
    RoomMessageEmote,
    RoomMessageNotice,
    RoomMessageText,
    UploadResponse,
    WhoamiError,
)
from nio.events.room_events import RoomMemberEvent
from PIL import Image

from mmrelay.config import get_base_dir, get_e2ee_store_dir, save_credentials
from mmrelay.constants.config import (
    CONFIG_SECTION_MATRIX,
)
from mmrelay.constants.database import DEFAULT_MSGS_TO_KEEP
from mmrelay.constants.formats import (
    DEFAULT_MATRIX_PREFIX,
    DEFAULT_MESHTASTIC_PREFIX,
    DETECTION_SENSOR_APP,
)
from mmrelay.constants.messages import (
    DEFAULT_MESSAGE_TRUNCATE_BYTES,
    DISPLAY_NAME_DEFAULT_LENGTH,
    MAX_TRUNCATION_LENGTH,
    MESHNET_NAME_ABBREVIATION_LENGTH,
    MESSAGE_PREVIEW_LENGTH,
    SHORTNAME_FALLBACK_LENGTH,
    TRUNCATION_LOG_LIMIT,
)
from mmrelay.constants.network import (
    MATRIX_EARLY_SYNC_TIMEOUT,
    MATRIX_LOGIN_TIMEOUT,
    MATRIX_MAIN_SYNC_TIMEOUT,
    MATRIX_ROOM_SEND_TIMEOUT,
    MATRIX_SYNC_OPERATION_TIMEOUT,
    MILLISECONDS_PER_SECOND,
)
from mmrelay.db_utils import (
    get_message_map_by_matrix_event_id,
    prune_message_map,
    store_message_map,
)
from mmrelay.log_utils import get_logger

# Do not import plugin_loader here to avoid circular imports
from mmrelay.meshtastic_utils import connect_meshtastic, sendTextReply
from mmrelay.message_queue import get_message_queue, queue_message

logger = get_logger(name="matrix_utils")


def _get_msgs_to_keep_config():
    """
    Returns the configured number of messages to retain for message mapping, supporting both current and legacy configuration sections.

    Returns:
        int: Number of messages to keep for message mapping; defaults to the predefined constant if not set.
    """
    global config
    if not config:
        return DEFAULT_MSGS_TO_KEEP

    msg_map_config = config.get("database", {}).get("msg_map", {})

    # If not found in database config, check legacy db config
    if not msg_map_config:
        legacy_msg_map_config = config.get("db", {}).get("msg_map", {})

        if legacy_msg_map_config:
            msg_map_config = legacy_msg_map_config
            logger.warning(
                "Using 'db.msg_map' configuration (legacy). 'database.msg_map' is now the preferred format and 'db.msg_map' will be deprecated in a future version."
            )

    return msg_map_config.get("msgs_to_keep", DEFAULT_MSGS_TO_KEEP)


def _create_mapping_info(
    matrix_event_id, room_id, text, meshnet=None, msgs_to_keep=None
):
    """
    Create a metadata dictionary linking a Matrix event to a Meshtastic message for message mapping.

    Removes quoted lines from the message text and includes identifiers and message retention settings. Returns `None` if any required parameter is missing.

    Returns:
        dict: Mapping information for the message queue, or `None` if required fields are missing.
    """
    if not matrix_event_id or not room_id or not text:
        return None

    if msgs_to_keep is None:
        msgs_to_keep = _get_msgs_to_keep_config()

    return {
        "matrix_event_id": matrix_event_id,
        "room_id": room_id,
        "text": strip_quoted_lines(text),
        "meshnet": meshnet,
        "msgs_to_keep": msgs_to_keep,
    }


def get_interaction_settings(config):
    """
    Determine if message reactions and replies are enabled in the configuration.

    Checks for both the new `message_interactions` structure and the legacy `relay_reactions` flag for backward compatibility. Returns a dictionary with boolean values for `reactions` and `replies`, defaulting to both disabled if not specified.
    """
    if config is None:
        return {"reactions": False, "replies": False}

    meshtastic_config = config.get("meshtastic", {})

    # Check for new structured configuration first
    if "message_interactions" in meshtastic_config:
        interactions = meshtastic_config["message_interactions"]
        return {
            "reactions": interactions.get("reactions", False),
            "replies": interactions.get("replies", False),
        }

    # Fall back to legacy relay_reactions setting
    if "relay_reactions" in meshtastic_config:
        enabled = meshtastic_config["relay_reactions"]
        logger.warning(
            "Configuration setting 'relay_reactions' is deprecated. "
            "Please use 'message_interactions: {reactions: bool, replies: bool}' instead. "
            "Legacy mode: enabling reactions only."
        )
        return {
            "reactions": enabled,
            "replies": False,
        }  # Only reactions for legacy compatibility

    # Default to privacy-first (both disabled)
    return {"reactions": False, "replies": False}


def message_storage_enabled(interactions):
    """
    Determine if message storage is needed based on enabled message interactions.

    Returns:
        True if either reactions or replies are enabled in the interactions dictionary; otherwise, False.
    """
    return interactions["reactions"] or interactions["replies"]


def _add_truncated_vars(format_vars, prefix, text):
    """Helper function to add variable length truncation variables to format_vars dict."""
    # Always add truncated variables, even for empty text (to prevent KeyError)
    text = text or ""  # Convert None to empty string
    logger.debug(f"Adding truncated vars for prefix='{prefix}', text='{text}'")
    for i in range(
        1, MAX_TRUNCATION_LENGTH + 1
    ):  # Support up to MAX_TRUNCATION_LENGTH chars, always add all variants
        truncated_value = text[:i]
        format_vars[f"{prefix}{i}"] = truncated_value
        if i <= TRUNCATION_LOG_LIMIT:  # Only log first few to avoid spam
            logger.debug(f"  {prefix}{i} = '{truncated_value}'")


def validate_prefix_format(format_string, available_vars):
    """Validate prefix format string against available variables.

    Args:
        format_string (str): The format string to validate.
        available_vars (dict): Dictionary of available variables with test values.

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    try:
        # Test format with dummy data
        format_string.format(**available_vars)
        return True, None
    except (KeyError, ValueError) as e:
        return False, str(e)


def get_meshtastic_prefix(config, display_name, user_id=None):
    """
    Generate a Meshtastic message prefix using the configured format, supporting variable-length truncation and user-specific variables.

    If prefix formatting is enabled in the configuration, returns a formatted prefix string for Meshtastic messages using the user's display name and optional Matrix user ID. Supports custom format strings with placeholders for the display name, truncated display name segments (e.g., `{display5}`), and user ID components. Falls back to a default format if the custom format is invalid or missing. Returns an empty string if prefixing is disabled.

    Args:
        config (dict): The application configuration dictionary.
        display_name (str): The user's display name (room-specific or global).
        user_id (str, optional): The user's Matrix ID (@user:server.com).

    Returns:
        str: The formatted prefix string if enabled, empty string otherwise.

    Examples:
        Basic usage:
            get_meshtastic_prefix(config, "Alice Smith")
            # Returns: "Alice[M]: " (with default format)

        Custom format:
            config = {"meshtastic": {"prefix_format": "{display8}> "}}
            get_meshtastic_prefix(config, "Alice Smith")
            # Returns: "Alice Sm> "
    """
    meshtastic_config = config.get("meshtastic", {})

    # Check if prefixes are enabled
    if not meshtastic_config.get("prefix_enabled", True):
        return ""

    # Get custom format or use default
    prefix_format = meshtastic_config.get("prefix_format", DEFAULT_MESHTASTIC_PREFIX)

    # Parse username and server from user_id if available
    username = ""
    server = ""
    if user_id:
        # Extract username and server from @username:server.com format
        if user_id.startswith("@") and ":" in user_id:
            parts = user_id[1:].split(":", 1)  # Remove @ and split on first :
            username = parts[0]
            server = parts[1] if len(parts) > 1 else ""

    # Available variables for formatting with variable length support
    format_vars = {
        "display": display_name or "",
        "user": user_id or "",
        "username": username,
        "server": server,
    }

    # Add variable length display name truncation (display1, display2, display3, etc.)
    _add_truncated_vars(format_vars, "display", display_name)

    try:
        return prefix_format.format(**format_vars)
    except (KeyError, ValueError) as e:
        # Fallback to default format if custom format is invalid
        logger.warning(
            f"Invalid prefix_format '{prefix_format}': {e}. Using default format."
        )
        # The default format only uses 'display5', which is safe to format
        return DEFAULT_MESHTASTIC_PREFIX.format(
            display5=display_name[:DISPLAY_NAME_DEFAULT_LENGTH] if display_name else ""
        )


def get_matrix_prefix(config, longname, shortname, meshnet_name):
    """
    Generates a formatted prefix string for Meshtastic messages relayed to Matrix, based on configuration settings and sender/mesh network names.

    The prefix format supports variable-length truncation for the sender and mesh network names using template variables (e.g., `{long4}` for the first 4 characters of the sender name). Returns an empty string if prefixing is disabled in the configuration.

    Parameters:
        longname (str): Full Meshtastic sender name.
        shortname (str): Short Meshtastic sender name.
        meshnet_name (str): Name of the mesh network.

    Returns:
        str: The formatted prefix string, or an empty string if prefixing is disabled.
    """
    matrix_config = config.get(CONFIG_SECTION_MATRIX, {})

    # Enhanced debug logging for configuration troubleshooting
    logger.debug(
        f"get_matrix_prefix called with longname='{longname}', shortname='{shortname}', meshnet_name='{meshnet_name}'"
    )
    logger.debug(f"Matrix config section: {matrix_config}")

    # Check if prefixes are enabled for Matrix direction
    if not matrix_config.get("prefix_enabled", True):
        logger.debug("Matrix prefixes are disabled, returning empty string")
        return ""

    # Get custom format or use default
    matrix_prefix_format = matrix_config.get("prefix_format", DEFAULT_MATRIX_PREFIX)
    logger.debug(
        f"Using matrix prefix format: '{matrix_prefix_format}' (default: '{DEFAULT_MATRIX_PREFIX}')"
    )

    # Available variables for formatting with variable length support
    format_vars = {
        "long": longname,
        "short": shortname,
        "mesh": meshnet_name,
    }

    # Add variable length truncation for longname and mesh name
    _add_truncated_vars(format_vars, "long", longname)
    _add_truncated_vars(format_vars, "mesh", meshnet_name)

    try:
        result = matrix_prefix_format.format(**format_vars)
        logger.debug(
            f"Matrix prefix generated: '{result}' using format '{matrix_prefix_format}' with vars {format_vars}"
        )
        # Additional debug to help identify the issue
        if result == f"[{longname}/{meshnet_name}]: ":
            logger.debug(
                "Generated prefix matches default format - check if custom configuration is being loaded correctly"
            )
        return result
    except (KeyError, ValueError) as e:
        # Fallback to default format if custom format is invalid
        logger.warning(
            f"Invalid matrix prefix_format '{matrix_prefix_format}': {e}. Using default format."
        )
        # The default format only uses 'long' and 'mesh', which are safe
        return DEFAULT_MATRIX_PREFIX.format(
            long=longname or "", mesh=meshnet_name or ""
        )


# Global config variable that will be set from config.py
config = None

# These will be set in connect_matrix()
matrix_homeserver = None
matrix_rooms = None
matrix_access_token = None
bot_user_id = None
bot_user_name = None  # Detected upon logon
bot_start_time = int(
    time.time() * MILLISECONDS_PER_SECOND
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

    # Check for simple !command format first
    if full_message.startswith(f"!{command}") or text_content.startswith(f"!{command}"):
        return True

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


async def connect_matrix(passed_config=None):
    """
    Establish a connection to the Matrix homeserver with optional E2EE support.

    Supports both legacy token-based authentication and new credentials.json-based E2EE setup.
    Returns the initialized Matrix AsyncClient instance, or None if configuration is missing.
    """
    global matrix_client, bot_user_name, matrix_homeserver, matrix_rooms, matrix_access_token, bot_user_id, config

    # Update the global config if a config is passed
    if passed_config is not None:
        config = passed_config

    # Check if config is available
    if config is None:
        logger.error("No configuration available. Cannot connect to Matrix.")
        return None

    # Check if client already exists
    if matrix_client:
        return matrix_client

    # Check for credentials.json first
    credentials = None
    credentials_path = None

    # Try to find credentials.json in the config directory
    try:
        from mmrelay.config import get_base_dir

        config_dir = get_base_dir()
        credentials_path = os.path.join(config_dir, "credentials.json")

        if os.path.exists(credentials_path):
            logger.info(f"Found credentials at {credentials_path}")
            with open(credentials_path, "r") as f:
                credentials = json.load(f)
    except Exception as e:
        logger.warning(f"Error loading credentials: {e}")

    # If credentials.json exists, use it
    if credentials:
        matrix_homeserver = credentials["homeserver"]
        matrix_access_token = credentials["access_token"]
        bot_user_id = credentials["user_id"]
        e2ee_device_id = credentials["device_id"]
        logger.info(f"Using credentials from {credentials_path}")
        # If config also has Matrix login info, let the user know we're ignoring it
        if config and "matrix" in config and "access_token" in config["matrix"]:
            logger.info(
                "NOTE: Ignoring Matrix login details in config.yaml in favor of credentials.json"
            )
    else:
        # Check if config is available
        if config is None:
            logger.error("No configuration available. Cannot connect to Matrix.")
            return None

        # Extract Matrix configuration from config
        matrix_homeserver = config["matrix"]["homeserver"]
        matrix_access_token = config["matrix"]["access_token"]
        bot_user_id = config["matrix"]["bot_user_id"]

    # Get matrix rooms from config
    matrix_rooms = config["matrix_rooms"]

    # Create SSL context using certifi's certificates
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except Exception as e:
        logger.error(f"Failed to create SSL context: {e}")
        raise ConnectionError(f"SSL context creation failed: {e}") from e

    # Check if E2EE is enabled
    e2ee_enabled = False
    e2ee_store_path = None
    e2ee_device_id = None

    try:
        # Check both 'encryption' and 'e2ee' keys for backward compatibility
        if (
            "encryption" in config["matrix"]
            and config["matrix"]["encryption"].get("enabled", False)
        ) or (
            "e2ee" in config["matrix"]
            and config["matrix"]["e2ee"].get("enabled", False)
        ):
            # Check if python-olm is installed
            try:
                import olm  # noqa: F401

                e2ee_enabled = True
                logger.info("End-to-End Encryption (E2EE) is enabled")

                # Get store path from config or use default
                if (
                    "encryption" in config["matrix"]
                    and "store_path" in config["matrix"]["encryption"]
                ):
                    e2ee_store_path = os.path.expanduser(
                        config["matrix"]["encryption"]["store_path"]
                    )
                elif (
                    "e2ee" in config["matrix"]
                    and "store_path" in config["matrix"]["e2ee"]
                ):
                    e2ee_store_path = os.path.expanduser(
                        config["matrix"]["e2ee"]["store_path"]
                    )
                else:
                    from mmrelay.config import get_e2ee_store_dir

                    e2ee_store_path = get_e2ee_store_dir()

                # Create store directory if it doesn't exist
                os.makedirs(e2ee_store_path, exist_ok=True)

                # Check if store directory contains database files
                store_files = (
                    os.listdir(e2ee_store_path)
                    if os.path.exists(e2ee_store_path)
                    else []
                )
                db_files = [f for f in store_files if f.endswith(".db")]
                if db_files:
                    logger.info(
                        f"Found existing E2EE store files: {', '.join(db_files)}"
                    )
                else:
                    logger.warning(
                        "No existing E2EE store files found. Encryption may not work correctly."
                    )

                logger.info(f"Using E2EE store path: {e2ee_store_path}")

                # We'll get the device ID from whoami() later
                e2ee_device_id = None
                logger.debug("Will retrieve device_id from whoami() response")
            except ImportError:
                logger.warning(
                    "E2EE is enabled in config but python-olm is not installed."
                )
                logger.warning("Install mmrelay[e2e] to use E2EE features.")
                e2ee_enabled = False
    except (KeyError, TypeError):
        # E2EE not configured
        pass

    # Initialize the Matrix client with custom SSL context
    client_config = AsyncClientConfig(
        encryption_enabled=e2ee_enabled, store_sync_tokens=True
    )

    # Log the device ID being used
    if e2ee_device_id:
        logger.info(f"Using device ID: {e2ee_device_id}")

    matrix_client = AsyncClient(
        homeserver=matrix_homeserver,
        user=bot_user_id,
        device_id=e2ee_device_id,  # Will be None if not specified in config or credentials
        store_path=e2ee_store_path if e2ee_enabled else None,
        config=client_config,
        ssl=ssl_context,
    )

    # Set the access_token and user_id using restore_login for better session management
    if credentials:
        # Use restore_login method for proper session restoration
        matrix_client.restore_login(
            user_id=bot_user_id,
            device_id=e2ee_device_id,
            access_token=matrix_access_token,
        )
        logger.info(
            f"Restored login session for {bot_user_id} with device {e2ee_device_id}"
        )
    else:
        # Fallback to direct assignment for legacy token-based auth
        matrix_client.access_token = matrix_access_token
        matrix_client.user_id = bot_user_id

    # =====================================================================
    # MATRIX E2EE IMPLEMENTATION - CRITICAL SEQUENCE
    # =====================================================================
    # The sequence of operations is critical for proper E2EE functionality:
    #
    # 1. First, perform an early lightweight sync to initialize rooms and subscriptions
    #    This is critical for message delivery to work properly. Without this sync,
    #    the client would have no known rooms when messages are sent, causing silent failures.
    #    This sync populates matrix_client.rooms with the room objects needed for message delivery.
    #
    # 2. After this initial sync, we'll retrieve the device_id, verify credentials,
    #    load the encryption store, and upload keys BEFORE the main sync.
    #
    # 3. Only then will we perform the main sync that updates encryption state.
    #
    # This sequence ensures both proper message delivery AND encryption.
    # =====================================================================

    # Step 1: Early lightweight sync to initialize rooms and subscriptions
    logger.info("Performing early lightweight sync to initialize rooms...")
    try:
        await asyncio.wait_for(
            matrix_client.sync(timeout=MATRIX_EARLY_SYNC_TIMEOUT),
            timeout=MATRIX_SYNC_OPERATION_TIMEOUT
        )
        logger.info(f"Early sync completed with {len(matrix_client.rooms)} rooms")
    except asyncio.TimeoutError:
        logger.error(f"Early sync timed out after {MATRIX_SYNC_OPERATION_TIMEOUT} seconds")
        raise

    # Retrieve the device_id using whoami() - this is critical for E2EE
    try:
        whoami_response = await asyncio.wait_for(
            matrix_client.whoami(),
            timeout=MATRIX_LOGIN_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"whoami() timed out after {MATRIX_LOGIN_TIMEOUT} seconds")
        whoami_response = None
    if whoami_response is None:
        logger.error("Failed to retrieve device_id: whoami() timed out")
        if e2ee_enabled:
            logger.error(
                "E2EE requires a valid device_id. E2EE may not work correctly."
            )
        # Don't reset the device_id to None if we already have one from credentials
        if not matrix_client.device_id:
            logger.error("No device_id available. E2EE will not work correctly.")
    elif isinstance(whoami_response, WhoamiError):
        logger.error(f"Failed to retrieve device_id: {whoami_response.message}")
        if e2ee_enabled:
            logger.error(
                "E2EE requires a valid device_id. E2EE may not work correctly."
            )
        # Don't reset the device_id to None if we already have one from credentials
        if not matrix_client.device_id:
            logger.error("No device_id available. E2EE will not work correctly.")
    else:
        # Check if the device_id from whoami matches our credentials
        server_device_id = whoami_response.device_id
        if server_device_id:
            if not matrix_client.device_id:
                # If we don't have a device_id from credentials, use the one from whoami
                matrix_client.device_id = server_device_id
                logger.info(f"Using device_id from server: {matrix_client.device_id}")

                # Update credentials.json with the correct device_id
                if credentials and credentials_path:
                    try:
                        credentials["device_id"] = server_device_id
                        with open(credentials_path, "w") as f:
                            json.dump(credentials, f)
                        logger.info(
                            f"Updated credentials.json with device_id: {server_device_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update credentials.json: {e}")
            elif matrix_client.device_id != server_device_id:
                # If the device_id from credentials doesn't match the server, update it
                logger.warning(
                    f"Device ID mismatch: credentials={matrix_client.device_id}, server={server_device_id}"
                )
                logger.info(f"Updating device_id to match server: {server_device_id}")
                matrix_client.device_id = server_device_id

                # Update credentials.json with the correct device_id
                if credentials and credentials_path:
                    try:
                        credentials["device_id"] = server_device_id
                        with open(credentials_path, "w") as f:
                            json.dump(credentials, f)
                        logger.info(
                            f"Updated credentials.json with device_id: {server_device_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update credentials.json: {e}")
            else:
                # Device IDs match, all good
                logger.info(f"Using verified device_id: {matrix_client.device_id}")
        else:
            logger.error(
                "No device_id returned by whoami(). E2EE will not work correctly."
            )

    # Fetch the bot's display name
    response = await matrix_client.get_displayname(bot_user_id)
    if hasattr(response, "displayname"):
        bot_user_name = response.displayname
    else:
        bot_user_name = bot_user_id  # Fallback if display name is not set

    # =====================================================================
    # MATRIX E2EE IMPLEMENTATION - ENCRYPTION SETUP
    # =====================================================================
    # This section handles the critical encryption setup sequence:
    # 1. Load the encryption store (contains keys and device information)
    # 2. Upload keys BEFORE performing the main sync
    # 3. Perform sync AFTER key upload
    # 4. Verify that rooms are properly populated
    #
    # This sequence is critical for proper encryption. If keys are not uploaded
    # before the first sync that handles encrypted messages, the first message
    # will fail to encrypt properly ("waiting for this message" error in Element).
    # =====================================================================

    # If E2EE is enabled, load the store and set up encryption
    if e2ee_enabled:
        try:
            # Check if store directory contains database files
            store_files = (
                os.listdir(e2ee_store_path) if os.path.exists(e2ee_store_path) else []
            )
            db_files = [f for f in store_files if f.endswith(".db")]
            if db_files:
                logger.info(f"Found existing E2EE store files: {', '.join(db_files)}")
            else:
                logger.warning(
                    "No existing E2EE store files found. Encryption may not work correctly."
                )

            # Load the store first
            logger.debug("Loading encryption store...")
            matrix_client.load_store()
            logger.debug("Encryption store loaded successfully")

            # Debug store state
            logger.debug(f"E2EE store path: {e2ee_store_path}")
            logger.debug(
                f"Device store users immediately after load: {list(matrix_client.device_store.users) if matrix_client.device_store else 'None'}"
            )

            # Confirm client credentials are set
            logger.debug(
                f"Checking client credentials: user_id={matrix_client.user_id}, device_id={matrix_client.device_id}"
            )
            if not (
                matrix_client.user_id
                and matrix_client.device_id
                and matrix_client.access_token
            ):
                logger.warning(
                    "Missing essential credentials for E2EE. Encryption may not work correctly."
                )

            # Upload keys BEFORE first sync
            logger.debug("Uploading encryption keys to server BEFORE sync")
            try:
                if matrix_client.should_upload_keys:
                    await matrix_client.keys_upload()
                    logger.debug("Encryption keys uploaded successfully")
                else:
                    logger.debug("No key upload needed at this stage")
            except Exception as ke:
                logger.warning(f"Error uploading keys: {ke}")

            # Now perform sync after keys are uploaded
            logger.debug("Performing sync AFTER key upload")
            try:
                await asyncio.wait_for(
                    matrix_client.sync(timeout=MATRIX_MAIN_SYNC_TIMEOUT),
                    timeout=MATRIX_SYNC_OPERATION_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.error(f"Sync after key upload timed out after {MATRIX_SYNC_OPERATION_TIMEOUT} seconds")
                # Continue anyway, don't fail completely

            # Debug store state after sync
            logger.debug(
                f"Device store users after sync: {list(matrix_client.device_store.users) if matrix_client.device_store else 'None'}"
            )

            # Verify that rooms are properly populated
            if not matrix_client.rooms:
                logger.warning(
                    "No rooms found after sync. Message delivery may not work correctly."
                )
            else:
                # Only log room info at debug level
                logger.debug(f"Found {len(matrix_client.rooms)} rooms after sync")
                logger.debug(f"Available rooms: {list(matrix_client.rooms.keys())}")

            # Trust all of our own devices to ensure encryption works
            logger.debug("Trusting our own devices for encryption...")
            try:
                # First make sure we have synced to populate the device store
                logger.debug("Performing sync to populate device store...")
                try:
                    await asyncio.wait_for(
                        matrix_client.sync(timeout=MATRIX_MAIN_SYNC_TIMEOUT),
                        timeout=MATRIX_SYNC_OPERATION_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Sync to populate device store timed out after {MATRIX_SYNC_OPERATION_TIMEOUT} seconds")
                    # Continue anyway, don't fail completely

                # Check if our user_id is in the device_store
                if (
                    matrix_client.device_store
                    and matrix_client.user_id in matrix_client.device_store
                ):
                    devices = matrix_client.device_store[matrix_client.user_id]
                    logger.info(
                        f"Found {len(devices)} of our own devices in the device store"
                    )

                    # Trust each of our devices
                    for device_id, device in devices.items():
                        # Skip our current device as we can't verify it
                        if device_id == matrix_client.device_id:
                            logger.debug(f"Skipping our current device: {device_id}")
                            continue

                        try:
                            matrix_client.verify_device(device)
                            logger.info(f"Trusted own device {device_id}")
                        except Exception as e:
                            logger.error(f"Failed to trust device {device_id}: {e}")

                    # Log about our current device
                    if matrix_client.device_id in devices:
                        logger.info(
                            f"Our current device is in the device store: {matrix_client.device_id}"
                        )
                    else:
                        logger.debug(
                            f"Our current device {matrix_client.device_id} not found in device store (this is normal)"
                        )
                else:
                    logger.debug(
                        "No devices found for our user in the device store (this is normal for first run)"
                    )
            except Exception as ve:
                logger.warning(f"Error verifying devices: {ve}")

            # Patch the client to handle unverified devices
            # This is a safer approach than monkey patching the OlmDevice class
            original_encrypt_for_devices = None
            if hasattr(matrix_client, "olm") and matrix_client.olm:
                if hasattr(matrix_client.olm, "encrypt_for_devices"):
                    original_encrypt_for_devices = matrix_client.olm.encrypt_for_devices

                    # Create a wrapper that ignores verification status
                    async def encrypt_for_all_devices(
                        room_id, users_devices, plaintext
                    ):
                        # Force ignore_unverified_devices=True
                        return await original_encrypt_for_devices(
                            room_id,
                            users_devices,
                            plaintext,
                            ignore_unverified_devices=True,
                        )

                    # Apply the patch
                    matrix_client.olm.encrypt_for_devices = encrypt_for_all_devices
                    logger.debug(
                        "Patched encrypt_for_devices to ignore verification status"
                    )

            logger.debug("E2EE setup complete - will encrypt for all devices")

        except Exception as e:
            logger.error(f"Error setting up E2EE: {e}")
            # Continue without E2EE if there's an error

    return matrix_client


async def login_matrix_bot(
    homeserver=None, username=None, password=None, logout_others=False
):
    """
    Login to Matrix as a bot and save the access token for E2EE use.

    This function creates a new Matrix session with E2EE support and saves
    the credentials to credentials.json for use by the relay.

    Args:
        homeserver: The Matrix homeserver URL
        username: The Matrix username
        password: The Matrix password
        logout_others: Whether to log out other sessions

    Returns:
        bool: True if login was successful, False otherwise
    """
    try:
        # Get homeserver URL
        if not homeserver:
            homeserver = input(
                "Enter Matrix homeserver URL (e.g., https://matrix.org): "
            )

        # Ensure homeserver URL has the correct format
        if not (homeserver.startswith("https://") or homeserver.startswith("http://")):
            homeserver = "https://" + homeserver

        # Get username
        if not username:
            username = input("Enter Matrix username (without @): ")

        # Format username correctly
        if not username.startswith("@"):
            username = f"@{username}"

        server_name = urlparse(homeserver).netloc
        if ":" not in username:
            username = f"{username}:{server_name}"

        logger.info(f"Using username: {username}")

        # Get password
        if not password:
            password = getpass.getpass("Enter Matrix password: ")

        # Ask about logging out other sessions
        if logout_others is None:
            logout_others_input = input(
                "Log out other sessions? (Y/n) [Default: Yes]: "
            ).lower()
            logout_others = (
                not logout_others_input.startswith("n") if logout_others_input else True
            )

        # Check for existing credentials to reuse device_id
        existing_device_id = None
        try:
            config_dir = get_base_dir()
            credentials_path = os.path.join(config_dir, "credentials.json")

            if os.path.exists(credentials_path):
                with open(credentials_path, "r") as f:
                    existing_creds = json.load(f)
                    if (
                        "device_id" in existing_creds
                        and existing_creds["user_id"] == username
                    ):
                        existing_device_id = existing_creds["device_id"]
                        logger.info(f"Reusing existing device_id: {existing_device_id}")
        except Exception as e:
            logger.debug(f"Could not load existing credentials: {e}")

        # Get the E2EE store path
        store_path = get_e2ee_store_dir()
        os.makedirs(store_path, exist_ok=True)
        logger.info(f"Using E2EE store path: {store_path}")

        # Create SSL context and client config for E2EE
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        client_config = AsyncClientConfig(
            store_sync_tokens=True, encryption_enabled=True
        )

        # Initialize client with E2EE support
        # Use positional arguments like the original working implementation
        client = AsyncClient(
            homeserver,
            username,
            device_id=existing_device_id,
            config=client_config,
            ssl=ssl_context,
            store_path=store_path,
        )

        logger.info(f"Logging in as {username} to {homeserver}...")

        # Login with consistent device name and timeout
        # Use the original working device name
        device_name = "mmrelay-e2ee"
        try:
            if existing_device_id:
                response = await asyncio.wait_for(
                    client.login(
                        password, device_name=device_name, device_id=existing_device_id
                    ),
                    timeout=MATRIX_LOGIN_TIMEOUT
                )
            else:
                response = await asyncio.wait_for(
                    client.login(password, device_name=device_name),
                    timeout=MATRIX_LOGIN_TIMEOUT
                )
        except asyncio.TimeoutError:
            logger.error(f"Login timed out after {MATRIX_LOGIN_TIMEOUT} seconds")
            logger.error("This may indicate network connectivity issues or a slow Matrix server")
            await client.close()
            return False
        except Exception as e:
            # Handle other exceptions during login (e.g., network errors)
            logger.error(f"Login exception: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, 'message'):
                logger.error(f"Exception message: {e.message}")
            await client.close()
            return False

        if hasattr(response, "access_token"):
            logger.info("Login successful!")

            # Save credentials to credentials.json
            credentials = {
                "homeserver": homeserver,
                "user_id": username,
                "access_token": response.access_token,
                "device_id": response.device_id,
            }

            config_dir = get_base_dir()
            credentials_path = os.path.join(config_dir, "credentials.json")
            save_credentials(credentials)
            logger.info(f"Credentials saved to {credentials_path}")

            # Logout other sessions if requested
            if logout_others:
                logger.info("Logging out other sessions...")
                # Note: This would require additional implementation
                logger.warning("Logout others not yet implemented")

            await client.close()
            return True
        else:
            # Better error logging
            logger.error(f"Login failed: {response}")
            if hasattr(response, 'message'):
                logger.error(f"Error message: {response.message}")
            if hasattr(response, 'status_code'):
                logger.error(f"Status code: {response.status_code}")
            await client.close()
            return False

    except Exception as e:
        logger.error(f"Error during login: {e}")
        return False


async def join_matrix_room(matrix_client, room_id_or_alias: str) -> None:
    """Join a Matrix room by its ID or alias."""
    try:
        if room_id_or_alias.startswith("#"):
            # If it's a room alias, resolve it to a room ID
            response = await matrix_client.room_resolve_alias(room_id_or_alias)
            if not hasattr(response, "room_id") or not response.room_id:
                logger.error(
                    f"Failed to resolve room alias '{room_id_or_alias}': {getattr(response, 'message', str(response))}"
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
    reply_to_event_id=None,
):
    """
    Relays a message from the Meshtastic network to a Matrix room, supporting replies, emotes, emoji reactions, and cross-network message mapping.

    If a reply target is specified, formats the message as a Matrix reply with appropriate quoting and HTML structure. Detects and preserves markdown or HTML formatting in outgoing messages, with graceful fallback if markdown processing is unavailable. When message interactions (reactions or replies) are enabled, stores a mapping between the Meshtastic message ID and the resulting Matrix event ID to support future cross-network interactions, pruning old mappings according to configuration.

    Parameters:
        room_id (str): The Matrix room ID to send the message to.
        message (str): The message content to relay.
        longname (str): The sender's long display name from Meshtastic.
        shortname (str): The sender's short display name from Meshtastic.
        meshnet_name (str): The originating meshnet name.
        portnum (int): The Meshtastic port number.
        meshtastic_id (str, optional): The Meshtastic message ID for mapping.
        meshtastic_replyId (str, optional): The Meshtastic message ID being replied to, if any.
        meshtastic_text (str, optional): The original Meshtastic message text.
        emote (bool, optional): Whether to send the message as an emote.
        emoji (bool, optional): Whether the message is an emoji reaction.
        reply_to_event_id (str, optional): The Matrix event ID being replied to, if sending a reply.
    """
    global config

    # Log the current state of the config
    logger.debug(f"matrix_relay: config is {'available' if config else 'None'}")

    matrix_client = await connect_matrix()

    # Check if config is available
    if config is None:
        logger.error("No configuration available. Cannot relay message to Matrix.")
        return

    # Get interaction settings
    interactions = get_interaction_settings(config)
    storage_enabled = message_storage_enabled(interactions)

    # Retrieve db config for message_map pruning
    # Check database config for message map settings (preferred format)
    database_config = config.get("database", {})
    msg_map_config = database_config.get("msg_map", {})

    # If not found in database config, check legacy db config
    if not msg_map_config:
        db_config = config.get("db", {})
        legacy_msg_map_config = db_config.get("msg_map", {})

        if legacy_msg_map_config:
            msg_map_config = legacy_msg_map_config
            logger.warning(
                "Using 'db.msg_map' configuration (legacy). 'database.msg_map' is now the preferred format and 'db.msg_map' will be deprecated in a future version."
            )
    msgs_to_keep = msg_map_config.get(
        "msgs_to_keep", DEFAULT_MSGS_TO_KEEP
    )  # Default from constants

    try:
        # Always use our own local meshnet_name for outgoing events
        local_meshnet_name = config["meshtastic"]["meshnet_name"]

        # Check if message contains HTML tags or markdown formatting
        has_html = bool(re.search(r"</?[a-zA-Z][^>]*>", message))
        has_markdown = bool(re.search(r"[*_`~]", message))  # Basic markdown indicators

        # Process markdown to HTML if needed (like base plugin does)
        if has_markdown or has_html:
            try:
                import markdown

                formatted_body = markdown.markdown(message)
                plain_body = re.sub(
                    r"</?[^>]*>", "", formatted_body
                )  # Strip all HTML tags
            except ImportError:
                # Fallback if markdown is not available
                formatted_body = message
                plain_body = message
                has_markdown = False
                has_html = False
        else:
            formatted_body = message
            plain_body = message

        content = {
            "msgtype": "m.text" if not emote else "m.emote",
            "body": plain_body,
            "meshtastic_longname": longname,
            "meshtastic_shortname": shortname,
            "meshtastic_meshnet": local_meshnet_name,
            "meshtastic_portnum": portnum,
        }

        # Add HTML formatting fields if message has markdown or HTML
        if has_markdown or has_html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = formatted_body
        if meshtastic_id is not None:
            content["meshtastic_id"] = meshtastic_id
        if meshtastic_replyId is not None:
            content["meshtastic_replyId"] = meshtastic_replyId
        if meshtastic_text is not None:
            content["meshtastic_text"] = meshtastic_text
        if emoji:
            content["meshtastic_emoji"] = 1

        # Add Matrix reply formatting if this is a reply
        if reply_to_event_id:
            content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to_event_id}}
            # For Matrix replies, we need to format the body with quoted content
            # Get the original message details for proper quoting
            try:
                orig = get_message_map_by_matrix_event_id(reply_to_event_id)
                if orig:
                    # orig = (meshtastic_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
                    _, _, original_text, original_meshnet = orig

                    # Use the relay bot's user ID for attribution (this is correct for relay messages)
                    bot_user_id = matrix_client.user_id
                    original_sender_display = f"{longname}/{original_meshnet}"

                    # Create the quoted reply format
                    quoted_text = f"> <@{bot_user_id}> [{original_sender_display}]: {original_text}"
                    content["body"] = f"{quoted_text}\n\n{plain_body}"

                    # Always use HTML formatting for replies since we need the mx-reply structure
                    content["format"] = "org.matrix.custom.html"
                    reply_link = f"https://matrix.to/#/{room_id}/{reply_to_event_id}"
                    bot_link = f"https://matrix.to/#/@{bot_user_id}"
                    blockquote_content = f'<a href="{reply_link}">In reply to</a> <a href="{bot_link}">@{bot_user_id}</a><br>[{original_sender_display}]: {original_text}'
                    content["formatted_body"] = (
                        f"<mx-reply><blockquote>{blockquote_content}</blockquote></mx-reply>{formatted_body}"
                    )
                else:
                    logger.warning(
                        f"Could not find original message for reply_to_event_id: {reply_to_event_id}"
                    )
            except Exception as e:
                logger.error(f"Error formatting Matrix reply: {e}")

        try:
            # Ensure matrix_client is not None
            if not matrix_client:
                logger.error("Matrix client is None. Cannot send message.")
                return

            # Send the message with a timeout
            # For encrypted rooms, use ignore_unverified_devices=True
            room = (
                matrix_client.rooms.get(room_id)
                if matrix_client and hasattr(matrix_client, "rooms")
                else None
            )
            ignore_unverified = getattr(room, "encrypted", False) if room else False

            response = await asyncio.wait_for(
                matrix_client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content=content,
                    ignore_unverified_devices=ignore_unverified,
                ),
                timeout=MATRIX_ROOM_SEND_TIMEOUT,  # Increased timeout
            )

            # Log at info level, matching one-point-oh pattern
            logger.info(f"Sent inbound radio message to matrix room: {room_id}")
            # Additional details at debug level
            if hasattr(response, "event_id"):
                logger.debug(f"Message event_id: {response.event_id}")

        except asyncio.TimeoutError:
            logger.error(f"Timeout sending message to Matrix room {room_id}")
            return
        except Exception as e:
            logger.error(f"Error sending message to Matrix room {room_id}: {e}")
            return

        # Only store message map if any interactions are enabled and conditions are met
        # This enables reactions and/or replies functionality based on configuration
        if (
            storage_enabled
            and meshtastic_id is not None
            and not emote
            and hasattr(response, "event_id")
        ):
            try:
                # Store the message map
                store_message_map(
                    meshtastic_id,
                    response.event_id,
                    room_id,
                    meshtastic_text if meshtastic_text else message,
                    meshtastic_meshnet=local_meshnet_name,
                )
                logger.debug(f"Stored message map for meshtastic_id: {meshtastic_id}")

                # If msgs_to_keep > 0, prune old messages after inserting a new one
                if msgs_to_keep > 0:
                    prune_message_map(msgs_to_keep)
            except Exception as e:
                logger.error(f"Error storing message map: {e}")

    except asyncio.TimeoutError:
        logger.error("Timed out while waiting for Matrix response")
    except Exception as e:
        logger.error(f"Error sending radio message to matrix room {room_id}: {e}")


def truncate_message(text, max_bytes=DEFAULT_MESSAGE_TRUNCATE_BYTES):
    """
    Truncate the given text to fit within the specified byte size.

    :param text: The text to truncate.
    :param max_bytes: The maximum allowed byte size for the truncated text.
    :return: The truncated text.
    """
    truncated_text = text.encode("utf-8")[:max_bytes].decode("utf-8", "ignore")
    return truncated_text


def strip_quoted_lines(text: str) -> str:
    """
    Removes lines starting with '>' from the input text.

    This is typically used to exclude quoted content from Matrix replies, such as when processing reaction text.
    """
    lines = text.splitlines()
    filtered = [line for line in lines if not line.strip().startswith(">")]
    return " ".join(filtered).strip()


async def get_user_display_name(room, event):
    """
    Retrieve the display name of a Matrix user, preferring the room-specific name if available.

    Returns:
        str: The user's display name, or their Matrix ID if no display name is set.
    """
    room_display_name = room.user_name(event.sender)
    if room_display_name:
        return room_display_name

    display_name_response = await matrix_client.get_displayname(event.sender)
    return display_name_response.displayname or event.sender


def format_reply_message(config, full_display_name, text):
    """
    Format a reply message by prefixing a truncated display name and removing quoted lines.

    The resulting message is prefixed with the first five characters of the user's display name followed by "[M]: ", has quoted lines removed, and is truncated to fit within the allowed message length.

    Parameters:
        full_display_name (str): The user's full display name to be truncated for the prefix.
        text (str): The reply text, possibly containing quoted lines.

    Returns:
        str: The formatted and truncated reply message.
    """
    prefix = get_meshtastic_prefix(config, full_display_name)

    # Strip quoted content from the reply text
    clean_text = strip_quoted_lines(text)
    reply_message = f"{prefix}{clean_text}"
    return truncate_message(reply_message)


async def send_reply_to_meshtastic(
    reply_message,
    full_display_name,
    room_config,
    room,
    event,
    text,
    storage_enabled,
    local_meshnet_name,
    reply_id=None,
):
    """
    Queues a reply message from Matrix to be sent to Meshtastic, optionally as a structured reply, and includes message mapping metadata if storage is enabled.

    If a `reply_id` is provided, the message is sent as a structured reply to the referenced Meshtastic message; otherwise, it is sent as a regular message. When message storage is enabled, mapping information is attached for future interaction tracking. The function logs the outcome of the queuing operation.
    """
    meshtastic_interface = connect_meshtastic()
    from mmrelay.meshtastic_utils import logger as meshtastic_logger

    meshtastic_channel = room_config["meshtastic_channel"]

    if config["meshtastic"]["broadcast_enabled"]:
        try:
            # Create mapping info once if storage is enabled
            mapping_info = None
            if storage_enabled:
                # Get message map configuration
                msgs_to_keep = _get_msgs_to_keep_config()

                mapping_info = _create_mapping_info(
                    event.event_id, room.room_id, text, local_meshnet_name, msgs_to_keep
                )

            if reply_id is not None:
                # Send as a structured reply using our custom function
                # Queue the reply message
                success = queue_message(
                    sendTextReply,
                    meshtastic_interface,
                    text=reply_message,
                    reply_id=reply_id,
                    channelIndex=meshtastic_channel,
                    description=f"Reply from {full_display_name} to message {reply_id}",
                    mapping_info=mapping_info,
                )

                if success:
                    # Get queue size to determine logging approach
                    queue_size = get_message_queue().get_queue_size()

                    if queue_size > 1:
                        meshtastic_logger.info(
                            f"Relaying Matrix reply from {full_display_name} to radio broadcast as structured reply (queued: {queue_size} messages)"
                        )
                    else:
                        meshtastic_logger.info(
                            f"Relaying Matrix reply from {full_display_name} to radio broadcast as structured reply"
                        )
                else:
                    meshtastic_logger.error(
                        "Failed to relay structured reply to Meshtastic"
                    )
                    return
            else:
                # Send as regular message (fallback for when no reply_id is available)
                success = queue_message(
                    meshtastic_interface.sendText,
                    text=reply_message,
                    channelIndex=meshtastic_channel,
                    description=f"Reply from {full_display_name} (fallback to regular message)",
                    mapping_info=mapping_info,
                )

                if success:
                    # Get queue size to determine logging approach
                    queue_size = get_message_queue().get_queue_size()

                    if queue_size > 1:
                        meshtastic_logger.info(
                            f"Relaying Matrix reply from {full_display_name} to radio broadcast (queued: {queue_size} messages)"
                        )
                    else:
                        meshtastic_logger.info(
                            f"Relaying Matrix reply from {full_display_name} to radio broadcast"
                        )
                else:
                    meshtastic_logger.error(
                        "Failed to relay reply message to Meshtastic"
                    )
                    return

            # Message mapping is now handled automatically by the queue system

        except Exception as e:
            meshtastic_logger.error(f"Error sending Matrix reply to Meshtastic: {e}")


async def handle_matrix_reply(
    room,
    event,
    reply_to_event_id,
    text,
    room_config,
    storage_enabled,
    local_meshnet_name,
    config,
):
    """
    Relays a Matrix reply to the corresponding Meshtastic message if a mapping exists.

    Looks up the original Meshtastic message using the Matrix event ID being replied to. If found, formats and sends the reply to Meshtastic, preserving conversational context. Returns True if the reply was successfully handled; otherwise, returns False to allow normal message processing.

    Returns:
        bool: True if the reply was relayed to Meshtastic, False otherwise.
    """
    # Look up the original message in the message map
    orig = get_message_map_by_matrix_event_id(reply_to_event_id)
    if not orig:
        logger.debug(
            f"Original message for Matrix reply not found in DB: {reply_to_event_id}"
        )
        return False  # Continue processing as normal message if original not found

    # Extract the original meshtastic_id to use as reply_id
    # orig = (meshtastic_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
    original_meshtastic_id = orig[0]

    # Get user display name
    full_display_name = await get_user_display_name(room, event)

    # Format the reply message
    reply_message = format_reply_message(config, full_display_name, text)

    logger.info(
        f"Relaying Matrix reply from {full_display_name} to Meshtastic as reply to message {original_meshtastic_id}"
    )

    # Send the reply to Meshtastic with the original message ID as reply_id
    await send_reply_to_meshtastic(
        reply_message,
        full_display_name,
        room_config,
        room,
        event,
        text,
        storage_enabled,
        local_meshnet_name,
        reply_id=original_meshtastic_id,
    )

    return True  # Reply was handled, stop further processing


# Callback for new messages in Matrix room
async def on_room_message(
    room: MatrixRoom,
    event: Union[
        RoomMessageText,
        RoomMessageNotice,
        ReactionEvent,
        RoomMessageEmote,
        MegolmEvent,
        RoomEncryptionEvent,
    ],
) -> None:
    """
    Asynchronously handles incoming Matrix room messages, reactions, and replies, relaying them to Meshtastic as appropriate.

    Processes Matrix events—including text messages, reactions, and replies—in configured rooms. Relays supported messages to the Meshtastic mesh network if broadcasting is enabled, applying message mapping for cross-referencing when reactions or replies are enabled. Ignores messages from the bot itself, messages sent before the bot started, and reactions to reactions. Integrates with plugins for command and message handling; only messages not handled by plugins or identified as commands are forwarded to Meshtastic, with appropriate formatting and truncation. Handles special cases for relaying messages and reactions from remote mesh networks and detection sensor data.
    """
    # Importing here to avoid circular imports and to keep logic consistent
    # Note: We do not call store_message_map directly here for inbound matrix->mesh messages.
    from mmrelay.message_queue import get_message_queue

    # That logic occurs inside matrix_relay if needed.
    full_display_name = "Unknown user"
    message_timestamp = event.server_timestamp

    # We do not relay messages that occurred before the bot started
    if message_timestamp < bot_start_time:
        return

    # Do not process messages from the bot itself
    if event.sender == bot_user_id:
        return

    # Handle RoomEncryptionEvent - log when a room becomes encrypted
    # Use string comparison for better test compatibility
    if (
        hasattr(event, "__class__")
        and event.__class__.__name__ == "RoomEncryptionEvent"
    ):
        logger.info(f"Room {room.room_id} is now encrypted")
        return

    # Handle MegolmEvent (encrypted messages)
    # Use string comparison for better test compatibility
    if hasattr(event, "__class__") and event.__class__.__name__ == "MegolmEvent":
        # If the event is encrypted but not yet decrypted, log and return
        if hasattr(event, "decrypted") and not event.decrypted:
            logger.warning(
                f"Received encrypted event that could not be decrypted in room {room.room_id}"
            )
            return

        # If decrypted, extract the decrypted event and process it
        logger.debug(f"Processing decrypted message in room {room.room_id}")
        # The decrypted event is available as event.decrypted_event
        # We need to recursively call this function with the decrypted event
        if hasattr(event, "decrypted_event") and event.decrypted_event:
            await on_room_message(room, event.decrypted_event)
        return

    # Find the room_config that matches this room, if any
    room_config = None
    for room_conf in matrix_rooms:
        if room_conf["id"] == room.room_id:
            room_config = room_conf
            break

    # Only proceed if the room is supported
    if not room_config:
        return

    relates_to = event.source["content"].get("m.relates_to")
    global config

    # Check if config is available
    if not config:
        logger.error("No configuration available for Matrix message processing.")

    is_reaction = False
    reaction_emoji = None
    original_matrix_event_id = None

    # Check if config is available
    if config is None:
        logger.error("No configuration available. Cannot process Matrix message.")
        return

    # Get interaction settings
    interactions = get_interaction_settings(config)
    storage_enabled = message_storage_enabled(interactions)

    # Check if this is a Matrix ReactionEvent (usually m.reaction)
    if isinstance(event, ReactionEvent):
        # This is a reaction event
        is_reaction = True
        logger.debug(f"Processing Matrix reaction event: {event.source}")
        if relates_to and "event_id" in relates_to and "key" in relates_to:
            # Extract the reaction emoji and the original event it relates to
            reaction_emoji = relates_to["key"]
            original_matrix_event_id = relates_to["event_id"]
            logger.debug(
                f"Original matrix event ID: {original_matrix_event_id}, Reaction emoji: {reaction_emoji}"
            )

    # Check if this is a Matrix RoomMessageEmote (m.emote)
    if isinstance(event, RoomMessageEmote):
        logger.debug(f"Processing Matrix reaction event: {event.source}")
        # For RoomMessageEmote, treat as remote reaction if meshtastic_replyId exists
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

    # If a message has suppress flag, do not process
    if suppress:
        return

    # If this is a reaction and reactions are disabled, do nothing
    if is_reaction and not interactions["reactions"]:
        logger.debug(
            "Reaction event encountered but reactions are disabled. Doing nothing."
        )
        return

    local_meshnet_name = config["meshtastic"]["meshnet_name"]

    # Check if this is a Matrix reply (not a reaction)
    is_reply = False
    reply_to_event_id = None
    if not is_reaction and relates_to and "m.in_reply_to" in relates_to:
        reply_to_event_id = relates_to["m.in_reply_to"].get("event_id")
        if reply_to_event_id:
            is_reply = True
            logger.debug(f"Processing Matrix reply to event: {reply_to_event_id}")

    # If this is a reaction and reactions are enabled, attempt to relay it
    if is_reaction and interactions["reactions"]:
        # Check if we need to relay a reaction from a remote meshnet to our local meshnet.
        # If meshnet_name != local_meshnet_name and meshtastic_replyId is present and this is an emote,
        # it's a remote reaction that needs to be forwarded as a text message describing the reaction.
        if (
            meshnet_name
            and meshnet_name != local_meshnet_name
            and meshtastic_replyId
            and isinstance(event, RoomMessageEmote)
        ):
            logger.info(f"Relaying reaction from remote meshnet: {meshnet_name}")

            short_meshnet_name = meshnet_name[:MESHNET_NAME_ABBREVIATION_LENGTH]

            # Format the reaction message for relaying to the local meshnet.
            # The necessary information is in the m.emote event
            if not shortname:
                shortname = longname[:SHORTNAME_FALLBACK_LENGTH] if longname else "???"

            meshtastic_text_db = event.source["content"].get("meshtastic_text", "")
            # Strip out any quoted lines from the text
            meshtastic_text_db = strip_quoted_lines(meshtastic_text_db)
            meshtastic_text_db = meshtastic_text_db.replace("\n", " ").replace(
                "\r", " "
            )

            abbreviated_text = (
                meshtastic_text_db[:MESSAGE_PREVIEW_LENGTH] + "..."
                if len(meshtastic_text_db) > MESSAGE_PREVIEW_LENGTH
                else meshtastic_text_db
            )

            reaction_message = f'{shortname}/{short_meshnet_name} reacted {reaction_emoji} to "{abbreviated_text}"'

            # Relay the remote reaction to the local meshnet.
            meshtastic_interface = connect_meshtastic()
            from mmrelay.meshtastic_utils import logger as meshtastic_logger

            meshtastic_channel = room_config["meshtastic_channel"]

            if config["meshtastic"]["broadcast_enabled"]:
                meshtastic_logger.info(
                    f"Relaying reaction from remote meshnet {meshnet_name} to radio broadcast"
                )
                logger.debug(
                    f"Sending reaction to Meshtastic with meshnet={local_meshnet_name}: {reaction_message}"
                )
                success = queue_message(
                    meshtastic_interface.sendText,
                    text=reaction_message,
                    channelIndex=meshtastic_channel,
                    description=f"Remote reaction from {meshnet_name}",
                )

                if success:
                    logger.debug(
                        f"Queued remote reaction to Meshtastic: {reaction_message}"
                    )
                else:
                    logger.error("Failed to relay remote reaction to Meshtastic")
                    return
            # We've relayed the remote reaction to our local mesh, so we're done.
            return

        # If original_matrix_event_id is set, this is a reaction to some other matrix event
        if original_matrix_event_id:
            orig = get_message_map_by_matrix_event_id(original_matrix_event_id)
            if not orig:
                # If we don't find the original message in the DB, we suspect it's a reaction-to-reaction scenario
                logger.debug(
                    "Original message for reaction not found in DB. Possibly a reaction-to-reaction scenario. Not forwarding."
                )
                return

            # orig = (meshtastic_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
            meshtastic_id, matrix_room_id, meshtastic_text_db, meshtastic_meshnet_db = (
                orig
            )
            # Get room-specific display name if available, fallback to global display name
            room_display_name = room.user_name(event.sender)
            if room_display_name:
                full_display_name = room_display_name
            else:
                # Fallback to global display name if room-specific name is not available
                display_name_response = await matrix_client.get_displayname(
                    event.sender
                )
                full_display_name = display_name_response.displayname or event.sender

            # If not from a remote meshnet, proceed as normal to relay back to the originating meshnet
            prefix = get_meshtastic_prefix(config, full_display_name)

            # Remove quoted lines so we don't bring in the original '>' lines from replies
            meshtastic_text_db = strip_quoted_lines(meshtastic_text_db)
            meshtastic_text_db = meshtastic_text_db.replace("\n", " ").replace(
                "\r", " "
            )

            abbreviated_text = (
                meshtastic_text_db[:MESSAGE_PREVIEW_LENGTH] + "..."
                if len(meshtastic_text_db) > MESSAGE_PREVIEW_LENGTH
                else meshtastic_text_db
            )

            # Always use our local meshnet_name for outgoing events
            reaction_message = (
                f'{prefix}reacted {reaction_emoji} to "{abbreviated_text}"'
            )
            meshtastic_interface = connect_meshtastic()
            from mmrelay.meshtastic_utils import logger as meshtastic_logger

            meshtastic_channel = room_config["meshtastic_channel"]

            if config["meshtastic"]["broadcast_enabled"]:
                meshtastic_logger.info(
                    f"Relaying reaction from {full_display_name} to radio broadcast"
                )
                logger.debug(
                    f"Sending reaction to Meshtastic with meshnet={local_meshnet_name}: {reaction_message}"
                )
                success = queue_message(
                    meshtastic_interface.sendText,
                    text=reaction_message,
                    channelIndex=meshtastic_channel,
                    description=f"Local reaction from {full_display_name}",
                )

                if success:
                    logger.debug(
                        f"Queued local reaction to Meshtastic: {reaction_message}"
                    )
                else:
                    logger.error("Failed to relay local reaction to Meshtastic")
                    return
            return

    # Handle Matrix replies to Meshtastic messages (only if replies are enabled)
    if is_reply and reply_to_event_id and interactions["replies"]:
        reply_handled = await handle_matrix_reply(
            room,
            event,
            reply_to_event_id,
            text,
            room_config,
            storage_enabled,
            local_meshnet_name,
            config,
        )
        if reply_handled:
            return

    # For Matrix->Mesh messages from a remote meshnet, rewrite the message format
    if longname and meshnet_name:
        # Always include the meshnet_name in the full display name.
        full_display_name = f"{longname}/{meshnet_name}"

        if meshnet_name != local_meshnet_name:
            # A message from a remote meshnet relayed into Matrix, now going back out
            logger.info(f"Processing message from remote meshnet: {meshnet_name}")
            short_meshnet_name = meshnet_name[:MESHNET_NAME_ABBREVIATION_LENGTH]
            # If shortname is not available, derive it from the longname
            if shortname is None:
                shortname = longname[:SHORTNAME_FALLBACK_LENGTH] if longname else "???"
            # Remove the original prefix to avoid double-tagging
            # Get the prefix that would have been used for this message
            original_prefix = get_matrix_prefix(
                config, longname, shortname, meshnet_name
            )
            if original_prefix and text.startswith(original_prefix):
                text = text[len(original_prefix) :]
                logger.debug(
                    f"Removed original prefix '{original_prefix}' from remote meshnet message"
                )
            text = truncate_message(text)
            # Use the configured prefix format for remote meshnet messages
            prefix = get_matrix_prefix(config, longname, shortname, short_meshnet_name)
            full_message = f"{prefix}{text}"
        else:
            # If this message is from our local meshnet (loopback), we ignore it
            return
    else:
        # Normal Matrix message from a Matrix user
        # Get room-specific display name if available, fallback to global display name
        room_display_name = room.user_name(event.sender)
        if room_display_name:
            full_display_name = room_display_name
        else:
            # Fallback to global display name if room-specific name is not available
            display_name_response = await matrix_client.get_displayname(event.sender)
            full_display_name = display_name_response.displayname or event.sender
        prefix = get_meshtastic_prefix(config, full_display_name, event.sender)
        logger.debug(f"Processing matrix message from [{full_display_name}]: {text}")
        full_message = f"{prefix}{text}"
        text = truncate_message(text)

    # Plugin functionality
    from mmrelay.plugin_loader import load_plugins

    plugins = load_plugins()

    found_matching_plugin = False
    for plugin in plugins:
        if not found_matching_plugin:
            try:
                found_matching_plugin = await plugin.handle_room_message(
                    room, event, full_message
                )
                if found_matching_plugin:
                    logger.info(
                        f"Processed command with plugin: {plugin.plugin_name} from {event.sender}"
                    )
            except Exception as e:
                logger.error(
                    f"Error processing message with plugin {plugin.plugin_name}: {e}"
                )

    # Check if the message is a command directed at the bot
    is_command = False
    for plugin in plugins:
        for command in plugin.get_matrix_commands():
            if bot_command(command, event):
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
    from mmrelay.meshtastic_utils import logger as meshtastic_logger

    if not meshtastic_interface:
        logger.error("Failed to connect to Meshtastic. Cannot relay message.")
        return

    meshtastic_channel = room_config["meshtastic_channel"]

    # If message is from Matrix and broadcast_enabled is True, relay to Meshtastic
    # Note: If relay_reactions is False, we won't store message_map, but we can still relay.
    # The lack of message_map storage just means no reaction bridging will occur.
    if not found_matching_plugin:
        if config["meshtastic"]["broadcast_enabled"]:
            portnum = event.source["content"].get("meshtastic_portnum")
            if portnum == DETECTION_SENSOR_APP:
                # If detection_sensor is enabled, forward this data as detection sensor data
                if config["meshtastic"].get("detection_sensor", False):
                    success = queue_message(
                        meshtastic_interface.sendData,
                        data=full_message.encode("utf-8"),
                        channelIndex=meshtastic_channel,
                        portNum=meshtastic.protobuf.portnums_pb2.PortNum.DETECTION_SENSOR_APP,
                        description=f"Detection sensor data from {full_display_name}",
                    )

                    if success:
                        # Get queue size to determine logging approach
                        queue_size = get_message_queue().get_queue_size()

                        if queue_size > 1:
                            meshtastic_logger.info(
                                f"Relaying detection sensor data from {full_display_name} to radio broadcast (queued: {queue_size} messages)"
                            )
                        else:
                            meshtastic_logger.info(
                                f"Relaying detection sensor data from {full_display_name} to radio broadcast"
                            )
                        # Note: Detection sensor messages are not stored in message_map because they are never replied to
                        # Only TEXT_MESSAGE_APP messages need to be stored for reaction handling
                    else:
                        meshtastic_logger.error(
                            "Failed to relay detection sensor data to Meshtastic"
                        )
                        return
                else:
                    meshtastic_logger.debug(
                        f"Detection sensor packet received from {full_display_name}, but detection sensor processing is disabled."
                    )
            else:
                # Regular text message - logging will be handled by queue success handler
                pass

                # Create mapping info if storage is enabled
                mapping_info = None
                if storage_enabled:
                    # Check database config for message map settings (preferred format)
                    msgs_to_keep = _get_msgs_to_keep_config()

                    mapping_info = _create_mapping_info(
                        event.event_id,
                        room.room_id,
                        text,
                        local_meshnet_name,
                        msgs_to_keep,
                    )

                success = queue_message(
                    meshtastic_interface.sendText,
                    text=full_message,
                    channelIndex=meshtastic_channel,
                    description=f"Message from {full_display_name}",
                    mapping_info=mapping_info,
                )

                if success:
                    # Get queue size to determine logging approach
                    queue_size = get_message_queue().get_queue_size()

                    if queue_size > 1:
                        meshtastic_logger.info(
                            f"Relaying message from {full_display_name} to radio broadcast (queued: {queue_size} messages)"
                        )
                    else:
                        meshtastic_logger.info(
                            f"Relaying message from {full_display_name} to radio broadcast"
                        )
                else:
                    meshtastic_logger.error("Failed to relay message to Meshtastic")
                    return
                # Message mapping is now handled automatically by the queue system
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


async def on_room_member(room: MatrixRoom, event: RoomMemberEvent) -> None:
    """
    Callback to handle room member events, specifically tracking room-specific display name changes.
    This ensures we detect when users update their display names in specific rooms.

    Note: This callback doesn't need to do any explicit processing since matrix-nio
    automatically updates the room state and room.user_name() will return the
    updated room-specific display name immediately after this event.
    """
    # The callback is registered to ensure matrix-nio processes the event,
    # but no explicit action is needed since room.user_name() automatically
    # handles room-specific display names after the room state is updated.
    pass
