import asyncio
import time
import meshtastic.tcp_interface
import meshtastic.serial_interface
import meshtastic.ble_interface
from typing import List
from config import relay_config
from log_utils import get_logger
from db_utils import get_longname, get_shortname
from plugin_loader import load_plugins
from bleak.exc import BleakDBusError, BleakError

# Extract matrix rooms configuration
matrix_rooms: List[dict] = relay_config["matrix_rooms"]

# Initialize logger
logger = get_logger(name="Meshtastic")

# Global variables
meshtastic_client = None
event_loop = None  # Will be set from main.py

def connect_meshtastic(force_connect=False):
    """
    Establish a connection to the Meshtastic device.

    Args:
        force_connect (bool): If True, forces a new connection even if one exists.

    Returns:
        The Meshtastic client interface or None if connection fails.
    """
    global meshtastic_client
    if meshtastic_client and not force_connect:
        return meshtastic_client

    # Ensure previous connection is closed
    if meshtastic_client:
        try:
            meshtastic_client.close()
        except Exception as e:
            logger.warning(f"Error closing previous connection: {e}")
        meshtastic_client = None

    # Initialize Meshtastic interface based on connection type
    connection_type = relay_config["meshtastic"]["connection_type"]
    retry_limit = relay_config["meshtastic"].get("retry_limit", 3)
    attempts = 1
    successful = False

    while not successful and attempts <= retry_limit:
        try:
            if connection_type == "serial":
                serial_port = relay_config["meshtastic"]["serial_port"]
                logger.info(f"Connecting to serial port {serial_port} ...")
                meshtastic_client = meshtastic.serial_interface.SerialInterface(serial_port)
            elif connection_type == "ble":
                ble_address = relay_config["meshtastic"].get("ble_address")
                if ble_address:
                    logger.info(f"Connecting to BLE address {ble_address} ...")
                    meshtastic_client = meshtastic.ble_interface.BLEInterface(
                        address=ble_address,
                        noProto=False,
                        debugOut=None,
                        noNodes=False
                    )
                else:
                    logger.error("No BLE address provided.")
                    return None
            else:
                target_host = relay_config["meshtastic"]["host"]
                logger.info(f"Connecting to host {target_host} ...")
                meshtastic_client = meshtastic.tcp_interface.TCPInterface(hostname=target_host)

            successful = True
            nodeInfo = meshtastic_client.getMyNodeInfo()
            logger.info(f"Connected to {nodeInfo['user']['shortName']} / {nodeInfo['user']['hwModel']}")

        except (BleakDBusError, BleakError, Exception) as e:
            attempts += 1
            if attempts <= retry_limit:
                logger.warning(f"Attempt #{attempts - 1} failed. Retrying in {attempts} secs {e}")
                time.sleep(attempts)
            else:
                logger.error(f"Could not connect: {e}")
                return None

    return meshtastic_client

def on_lost_meshtastic_connection(interface=None):
    """
    Callback function invoked when the Meshtastic connection is lost.

    Args:
        interface: The Meshtastic interface instance (unused).
    """
    logger.error("Lost connection. Reconnecting...")
    global event_loop
    if event_loop:
        asyncio.run_coroutine_threadsafe(reconnect(), event_loop)

async def reconnect():
    """
    Asynchronously attempts to reconnect to the Meshtastic device with exponential backoff.
    """
    backoff_time = 10
    while True:
        try:
            logger.info(f"Reconnection attempt starting in {backoff_time} seconds...")
            await asyncio.sleep(backoff_time)
            meshtastic_client = connect_meshtastic(force_connect=True)
            if meshtastic_client:
                logger.info("Reconnected successfully.")
                break
        except Exception as e:
            logger.error(f"Reconnection attempt failed: {e}")
            backoff_time = min(backoff_time * 2, 300)  # Cap backoff at 5 minutes

def on_meshtastic_message(packet, interface):
    """
    Handle incoming Meshtastic messages and relay them to Matrix.

    Args:
        packet (dict): The packet received from Meshtastic.
        interface: The Meshtastic interface instance.
    """
    from matrix_utils import matrix_relay
    global event_loop

    if event_loop is None:
        logger.error("Event loop is not set. Cannot process message.")
        return

    loop = event_loop

    sender = packet.get("fromId", packet.get("from"))

    decoded = packet.get("decoded", {})
    text = decoded.get("text")

    if text:
        # Determine the channel
        channel = packet.get("channel")
        if channel is None:
            if decoded.get("portnum") == "TEXT_MESSAGE_APP" or decoded.get("portnum") == 1:
                channel = 0
            else:
                logger.debug(f"Unknown portnum {decoded.get('portnum')}, cannot determine channel")
                return

        # Check if the channel is mapped to a Matrix room
        channel_mapped = False
        for room in matrix_rooms:
            if room["meshtastic_channel"] == channel:
                channel_mapped = True
                break

        if not channel_mapped:
            logger.debug(f"Skipping message from unmapped channel {channel}")
            return

        logger.info(f"Processing inbound radio message from {sender} on channel {channel}")

        longname = get_longname(sender) or sender
        shortname = get_shortname(sender) or sender
        meshnet_name = relay_config["meshtastic"]["meshnet_name"]

        formatted_message = f"[{longname}/{meshnet_name}]: {text}"

        # Plugin functionality
        plugins = load_plugins()
        found_matching_plugin = False
        for plugin in plugins:
            if not found_matching_plugin:
                result = asyncio.run_coroutine_threadsafe(
                    plugin.handle_meshtastic_message(
                        packet, formatted_message, longname, meshnet_name
                    ),
                    loop=loop,
                )
                found_matching_plugin = result.result()
                if found_matching_plugin:
                    logger.debug(f"Processed by plugin {plugin.plugin_name}")

        if found_matching_plugin:
            return

        logger.info(f"Relaying Meshtastic message from {longname} to Matrix")

        # Relay message to Matrix rooms
        for room in matrix_rooms:
            if room["meshtastic_channel"] == channel:
                asyncio.run_coroutine_threadsafe(
                    matrix_relay(
                        room["id"],
                        formatted_message,
                        longname,
                        shortname,
                        meshnet_name,
                    ),
                    loop=loop,
                )
    else:
        # Handle non-text messages if necessary
        portnum = decoded.get("portnum")
        logger.debug(f"Received non-text message on port {portnum}")

async def check_connection():
    """
    Periodically checks the Meshtastic connection and attempts to reconnect if lost.
    """
    global meshtastic_client
    connection_type = relay_config["meshtastic"]["connection_type"]
    while True:
        if meshtastic_client:
            try:
                # Use getMetadata to check the connection
                meshtastic_client.localNode.getMetadata()
            except Exception as e:
                logger.error(f"{connection_type.capitalize()} connection lost: {e}")
                on_lost_meshtastic_connection(meshtastic_client)
        await asyncio.sleep(5)  # Check connection every 5 seconds

if __name__ == "__main__":
    meshtastic_client = connect_meshtastic()
    loop = asyncio.get_event_loop()
    event_loop = loop  # Set the event loop
    loop.create_task(check_connection())
    loop.run_forever()
