import asyncio
import contextlib
import io
import threading
import time
from typing import List

import meshtastic.ble_interface
import meshtastic.serial_interface
import meshtastic.tcp_interface
import serial  # For serial port exceptions
import serial.tools.list_ports  # Import serial tools for port listing
from bleak.exc import BleakDBusError, BleakError
from pubsub import pub

from config import relay_config
from db_utils import (
    get_longname,
    get_message_map_by_meshtastic_id,
    get_shortname,
    save_longname,
    save_shortname,
)
from log_utils import get_logger

# Do not import plugin_loader here to avoid circular imports

# Extract matrix rooms configuration
matrix_rooms: List[dict] = relay_config["matrix_rooms"]

# Initialize logger for Meshtastic
logger = get_logger(name="Meshtastic")

# Global variables for the Meshtastic connection and event loop management
meshtastic_client = None
event_loop = None  # Will be set from main.py

meshtastic_lock = (
    threading.Lock()
)  # To prevent race conditions on meshtastic_client access

reconnecting = False
shutting_down = False
reconnect_task = None  # To keep track of the reconnect task


def serial_port_exists(port_name):
    """
    Check if the specified serial port exists.
    This prevents attempting connections on non-existent ports.
    """
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return port_name in ports


def connect_meshtastic(force_connect=False):
    """
    Establish a connection to the Meshtastic device.
    Attempts a connection based on connection_type (serial/ble/network).
    Retries until successful or shutting_down is set.
    If already connected and not force_connect, returns the existing client.
    """
    global meshtastic_client, shutting_down
    if shutting_down:
        logger.debug("Shutdown in progress. Not attempting to connect.")
        return None

    with meshtastic_lock:
        if meshtastic_client and not force_connect:
            return meshtastic_client

        # Close previous connection if exists
        if meshtastic_client:
            try:
                meshtastic_client.close()
            except Exception as e:
                logger.warning(f"Error closing previous connection: {e}")
            meshtastic_client = None

        # Determine connection type and attempt connection
        connection_type = relay_config["meshtastic"]["connection_type"]
        retry_limit = 0  # 0 means infinite retries
        attempts = 1
        successful = False

        while (
            not successful
            and (retry_limit == 0 or attempts <= retry_limit)
            and not shutting_down
        ):
            try:
                if connection_type == "serial":
                    # Serial connection
                    serial_port = relay_config["meshtastic"]["serial_port"]
                    logger.info(f"Connecting to serial port {serial_port} ...")

                    # Check if serial port exists before connecting
                    if not serial_port_exists(serial_port):
                        logger.warning(
                            f"Serial port {serial_port} does not exist. Waiting..."
                        )
                        time.sleep(5)
                        attempts += 1
                        continue

                    meshtastic_client = meshtastic.serial_interface.SerialInterface(
                        serial_port
                    )

                elif connection_type == "ble":
                    # BLE connection
                    ble_address = relay_config["meshtastic"].get("ble_address")
                    if ble_address:
                        logger.info(f"Connecting to BLE address {ble_address} ...")
                        meshtastic_client = meshtastic.ble_interface.BLEInterface(
                            address=ble_address,
                            noProto=False,
                            debugOut=None,
                            noNodes=False,
                        )
                    else:
                        logger.error("No BLE address provided.")
                        return None

                else:
                    # Network (TCP) connection
                    target_host = relay_config["meshtastic"]["host"]
                    logger.info(f"Connecting to host {target_host} ...")
                    meshtastic_client = meshtastic.tcp_interface.TCPInterface(
                        hostname=target_host
                    )

                successful = True
                nodeInfo = meshtastic_client.getMyNodeInfo()
                logger.info(
                    f"Connected to {nodeInfo['user']['shortName']} / {nodeInfo['user']['hwModel']}"
                )

                # Subscribe to message and connection lost events
                pub.subscribe(on_meshtastic_message, "meshtastic.receive")
                pub.subscribe(
                    on_lost_meshtastic_connection, "meshtastic.connection.lost"
                )

            except (
                serial.SerialException,
                BleakDBusError,
                BleakError,
                Exception,
            ) as e:
                if shutting_down:
                    logger.debug("Shutdown in progress. Aborting connection attempts.")
                    break
                attempts += 1
                if retry_limit == 0 or attempts <= retry_limit:
                    wait_time = min(
                        attempts * 2, 30
                    )  # Exponential backoff capped at 30s
                    logger.warning(
                        f"Attempt #{attempts - 1} failed. Retrying in {wait_time} secs: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Could not connect after {retry_limit} attempts: {e}")
                    return None

    return meshtastic_client


def on_lost_meshtastic_connection(interface=None):
    """
    Callback invoked when the Meshtastic connection is lost.
    Initiates a reconnect sequence unless shutting_down is True.
    """
    global meshtastic_client, reconnecting, shutting_down, event_loop, reconnect_task
    with meshtastic_lock:
        if shutting_down:
            logger.debug("Shutdown in progress. Not attempting to reconnect.")
            return
        if reconnecting:
            logger.debug(
                "Reconnection already in progress. Skipping additional reconnection attempt."
            )
            return
        reconnecting = True
        logger.error("Lost connection. Reconnecting...")

        if meshtastic_client:
            try:
                meshtastic_client.close()
            except OSError as e:
                if e.errno == 9:
                    # Bad file descriptor, already closed
                    pass
                else:
                    logger.warning(f"Error closing Meshtastic client: {e}")
            except Exception as e:
                logger.warning(f"Error closing Meshtastic client: {e}")
        meshtastic_client = None

        if event_loop:
            reconnect_task = asyncio.run_coroutine_threadsafe(reconnect(), event_loop)


async def reconnect():
    """
    Asynchronously attempts to reconnect with exponential backoff.
    Stops if shutting_down is set.
    """
    global meshtastic_client, reconnecting, shutting_down
    backoff_time = 10
    try:
        while not shutting_down:
            try:
                logger.info(
                    f"Reconnection attempt starting in {backoff_time} seconds..."
                )
                await asyncio.sleep(backoff_time)
                if shutting_down:
                    logger.debug(
                        "Shutdown in progress. Aborting reconnection attempts."
                    )
                    break
                meshtastic_client = connect_meshtastic(force_connect=True)
                if meshtastic_client:
                    logger.info("Reconnected successfully.")
                    break
            except Exception as e:
                if shutting_down:
                    break
                logger.error(f"Reconnection attempt failed: {e}")
                backoff_time = min(backoff_time * 2, 300)  # Cap backoff at 5 minutes
    except asyncio.CancelledError:
        logger.info("Reconnection task was cancelled.")
    finally:
        reconnecting = False


def on_meshtastic_message(packet, interface):
    """
    Handle incoming Meshtastic messages. For reaction messages, if relay_reactions is False,
    we do not store message maps and thus won't be able to relay reactions back to Matrix.
    If relay_reactions is True, message maps are stored inside matrix_relay().
    """
    # Apply reaction filtering based on config
    relay_reactions = relay_config["meshtastic"].get("relay_reactions", False)

    decoded = packet.get("decoded", {}) # Decode early
    portnum = decoded.get("portnum") # Get portnum

    # Convert portnum enum name (string) to its standard string representation if needed
    # Or just pass it as is, matrix_relay will handle it.
    # Example: portnum might be 'TEXT_MESSAGE_APP' or 1
    if isinstance(portnum, int):
        try:
            portnum_name = meshtastic.protobuf.portnums_pb2.PortNum.Name(portnum)
        except ValueError:
            portnum_name = str(portnum) # Fallback to number if unknown
    else:
        portnum_name = str(portnum) # Assume it's already a string or suitable representation


    # If relay_reactions is False, filter out reaction/tapback packets to avoid complexity
    if portnum_name == "TEXT_MESSAGE_APP": # Check using standard name
        if not relay_reactions and ("emoji" in decoded or "replyId" in decoded):
            logger.debug(
                "Filtered out reaction/tapback packet due to relay_reactions=false."
            )
            return

    # Import matrix_relay locally inside the function to ensure it's the updated version
    # and avoid top-level circular dependency issues.
    try:
        from matrix_utils import matrix_relay
    except ImportError:
        logger.error("Could not import matrix_relay. Cannot process message.")
        # This might indicate a deeper setup issue
        return


    global event_loop

    if shutting_down:
        logger.debug("Shutdown in progress. Ignoring incoming messages.")
        return

    if event_loop is None:
        logger.error("Event loop is not set. Cannot process message.")
        return

    loop = event_loop

    sender = packet.get("fromId") or packet.get("from")
    toId = packet.get("to")

    # decoded = packet.get("decoded", {}) # Already done above
    text = decoded.get("text")
    replyId = decoded.get("replyId")
    emoji_flag = "emoji" in decoded and decoded["emoji"] == 1 # Check for explicit emoji flag

    # Determine if this is a direct message to the relay node
    from meshtastic.mesh_interface import BROADCAST_NUM

    myId = interface.myInfo.my_node_num

    if toId == myId:
        is_direct_message = True
    elif toId == BROADCAST_NUM:
        is_direct_message = False
    else:
        # Message to someone else; ignoring for broadcasting logic
        is_direct_message = False

    meshnet_name = relay_config["meshtastic"]["meshnet_name"] # Our local meshnet name

    # Reaction handling (Meshtastic -> Matrix)
    # If replyId and emoji_flag are present and relay_reactions is True, we relay as text reactions in Matrix
    if replyId and emoji_flag and relay_reactions:
        longname = get_longname(sender) or str(sender)
        shortname = get_shortname(sender) or str(sender)
        orig = get_message_map_by_meshtastic_id(replyId)
        if orig:
            # orig = (matrix_event_id, matrix_room_id, meshtastic_text, meshtastic_meshnet)
            matrix_event_id, matrix_room_id, meshtastic_text, meshtastic_meshnet_origin = orig
            abbreviated_text = (
                meshtastic_text[:40] + "..."
                if len(meshtastic_text) > 40
                else meshtastic_text
            )
            abbreviated_text = abbreviated_text.replace("\n", " ").replace("\r", " ")


            # Ensure that meshnet_name is always included, using our own meshnet for accuracy.
            full_display_name = f"{longname}/{meshnet_name}"

            # Text should contain the emoji itself for reactions
            reaction_symbol = text.strip() if (text and text.strip()) else "⚠️" # Default emoji if missing
            # Format as an emote describing the action
            reaction_message = f'\n [{full_display_name}] reacted {reaction_symbol} to "{abbreviated_text}"'
            # Note: Matrix clients usually render m.emote differently than plain text.

            logger.info(f"Relaying Meshtastic reaction from {longname} to Matrix room {matrix_room_id}")

            # Relay the reaction as emote to Matrix, preserving the original meshnet name context if needed
            # The `matrix_relay` function now puts custom data inside content['dev.meshtastic.relay']
            asyncio.run_coroutine_threadsafe(
                matrix_relay(
                    matrix_room_id,
                    reaction_message, # This is the body of the m.emote
                    longname,
                    shortname,
                    meshnet_name, # Our local meshnet name as context for this relay event
                    portnum_name, # Pass the portnum string/name
                    meshtastic_id=packet.get("id"), # ID of the reaction packet itself
                    meshtastic_replyId=replyId, # ID of the message being reacted to
                    meshtastic_text=meshtastic_text, # Original text being reacted to (for context in Matrix event)
                    emote=True, # Send as m.emote
                    emoji=True, # Flag indicating this emote represents an emoji reaction
                ),
                loop=loop,
            )
        else:
            logger.debug(f"Original message {replyId} for reaction {packet.get('id')} not found in DB.")
        return # Reaction handled (or skipped)

    # Normal text messages or detection sensor messages
    if text:
        # Determine the channel for this message
        channel = packet.get("channel")
        if channel is None:
             # Based on portnum - This is a guess!
             if portnum_name == "TEXT_MESSAGE_APP":
                 channel = 0 # Often default channel
             elif portnum_name == "DETECTION_SENSOR_APP":
                 channel = 0 # Often default channel
             # Add other portnum -> channel mappings if known
             else:
                 logger.debug(
                     f"Unknown portnum {portnum_name} for packet {packet.get('id')}, cannot determine channel. Assuming 0."
                 )
                 channel = 0 # Default fallback


        # Check if channel is mapped to a Matrix room
        channel_mapped = False
        target_rooms = []
        for room_config in matrix_rooms:
            if room_config["meshtastic_channel"] == channel:
                channel_mapped = True
                target_rooms.append(room_config["id"])


        if not channel_mapped:
            logger.debug(f"Skipping message from unmapped channel index {channel} (packet {packet.get('id')})")
            return

        # If detection_sensor is disabled and this is a detection sensor packet, skip it
        if portnum_name == "DETECTION_SENSOR_APP" and not relay_config["meshtastic"].get("detection_sensor", False):
            logger.debug(
                f"Detection sensor packet {packet.get('id')} received, but detection sensor processing is disabled. Skipping."
            )
            return

        # Attempt to get longname/shortname from database or nodes
        longname = get_longname(sender)
        shortname = get_shortname(sender)

        # If name still missing, try fetching from node info (might be slow/blocking)
        # Consider doing this less frequently or caching more aggressively
        if not longname or not shortname:
            node = interface.nodes.get(sender) # Check local node cache
            if node:
                user = node.get("user")
                if user:
                    if not longname:
                        longname_val = user.get("longName")
                        if longname_val:
                            save_longname(sender, longname_val)
                            longname = longname_val
                    if not shortname:
                        shortname_val = user.get("shortName")
                        if shortname_val:
                            save_shortname(sender, shortname_val)
                            shortname = shortname_val
            else:
                # Optionally trigger a node info request if missing? Be careful with radio traffic.
                logger.debug(f"Node info for sender {sender} not available locally yet.")

        # Fallback to sender ID if names still unavailable
        if not longname:
            longname = f"!{sender[1:]}" # Use Meshtastic ID format
        if not shortname:
            shortname = longname[:3] # Use first 3 chars of longname/ID

        # Format message for Matrix relay, including meshnet name
        formatted_message = f"[{longname}/{meshnet_name}]: {text}"

        # Plugin functionality - Check if any plugin handles this message before relaying
        from plugin_loader import load_plugins
        plugins = load_plugins()

        found_matching_plugin = False
        for plugin in plugins:
            if not found_matching_plugin:
                 try:
                      # Run plugin handling in threadsafe manner
                      future = asyncio.run_coroutine_threadsafe(
                          plugin.handle_meshtastic_message(
                              packet, formatted_message, longname, meshnet_name
                          ),
                          loop=loop,
                      )
                      # Wait for result with a timeout to avoid blocking indefinitely
                      handled = future.result(timeout=5.0)
                      if handled:
                           found_matching_plugin = True
                           logger.debug(f"Message {packet.get('id')} processed by plugin {plugin.plugin_name}")
                 except asyncio.TimeoutError:
                      logger.warning(f"Plugin {plugin.plugin_name} timed out handling message {packet.get('id')}")
                 except Exception as e:
                      logger.error(f"Error executing handle_meshtastic_message for plugin {plugin.plugin_name}: {e}")

        # If message is a DM to the bot OR handled by plugin, do not relay further to Matrix rooms
        if is_direct_message:
            # Note: DM handling by plugins might still occur above. This prevents broadcasting DMs.
            logger.debug(
                f"Received a direct message {packet.get('id')} from {longname}. Not broadcasting to Matrix rooms."
            )
            # Plugins might still respond directly via matrix_relay if needed
            return
        if found_matching_plugin:
            logger.debug(f"Message {packet.get('id')} was handled by a plugin. Not broadcasting to Matrix rooms.")
            return

        # Relay the message to all Matrix rooms mapped to this channel
        logger.info(
            f"Processing inbound radio message {packet.get('id')} from {sender} on channel {channel}"
        )
        logger.info(f"Relaying Meshtastic message from {longname} to {len(target_rooms)} Matrix room(s)")
        for room_id in target_rooms:
            # Storing the message_map (if enabled) occurs inside matrix_relay() now,
            # controlled by relay_reactions. matrix_relay handles E2EE.
            asyncio.run_coroutine_threadsafe(
                matrix_relay(
                    room_id,
                    formatted_message,
                    longname,
                    shortname,
                    meshnet_name, # Our local meshnet name context
                    portnum_name, # Pass portnum string/name
                    meshtastic_id=packet.get("id"),
                    meshtastic_text=text, # Original text for storage/context
                    # emote and emoji are False for regular text
                ),
                loop=loop,
            )
    else:
        # Non-text messages (e.g., position, nodeinfo updates) potentially handled by plugins
        # portnum = decoded.get("portnum") # Already have portnum_name
        from plugin_loader import load_plugins
        plugins = load_plugins()
        found_matching_plugin = False
        for plugin in plugins:
            if not found_matching_plugin:
                 try:
                      # Pass packet, no formatted message for non-text
                      future = asyncio.run_coroutine_threadsafe(
                          plugin.handle_meshtastic_message(
                              packet,
                              formatted_message=None,
                              longname=get_longname(sender) or f"!{sender[1:]}", # Provide name context if possible
                              meshnet_name=meshnet_name,
                          ),
                          loop=loop,
                      )
                      handled = future.result(timeout=5.0)
                      if handled:
                           found_matching_plugin = True
                           logger.debug(
                               f"Processed non-text packet {packet.get('id')} ({portnum_name}) with plugin {plugin.plugin_name}"
                           )
                 except asyncio.TimeoutError:
                      logger.warning(f"Plugin {plugin.plugin_name} timed out handling non-text packet {packet.get('id')}")
                 except Exception as e:
                      logger.error(f"Error executing handle_meshtastic_message for plugin {plugin.plugin_name} on non-text packet: {e}")


async def check_connection():
    """
    Periodically checks the Meshtastic connection by calling localNode.getMetadata().
    If it fails or doesn't return the firmware version, we assume the connection is lost
    and attempt to reconnect.
    """
    global meshtastic_client, shutting_down
    connection_type = relay_config["meshtastic"]["connection_type"]
    while not shutting_down:
        if meshtastic_client:
            try:
                output_capture = io.StringIO()
                with contextlib.redirect_stdout(
                    output_capture
                ), contextlib.redirect_stderr(output_capture):
                    meshtastic_client.localNode.getMetadata()

                console_output = output_capture.getvalue()
                if "firmware_version" not in console_output:
                    raise Exception("No firmware_version in getMetadata output.")

            except Exception as e:
                logger.error(f"{connection_type.capitalize()} connection lost: {e}")
                on_lost_meshtastic_connection(meshtastic_client)
        await asyncio.sleep(30)  # Check connection every 30 seconds


if __name__ == "__main__":
    # If running this standalone (normally the main.py does the loop), just try connecting and run forever.
    meshtastic_client = connect_meshtastic()
    loop = asyncio.get_event_loop()
    event_loop = loop  # Set the event loop for use in callbacks
    loop.create_task(check_connection())
    loop.run_forever()
