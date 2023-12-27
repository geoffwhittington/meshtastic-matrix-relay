import asyncio
import time
import meshtastic.tcp_interface
import meshtastic.serial_interface
from typing import List
from asyncio import Lock
from config import relay_config
from log_utils import get_logger
from db_utils import get_longname, get_shortname
from plugin_loader import load_plugins

matrix_rooms: List[dict] = relay_config["matrix_rooms"]
logger = get_logger(name="Meshtastic")
meshtastic_client = None

reconnection_lock = Lock()

# Define the global flag
reconnect_needed = False  # This will act as a flag to indicate reconnection requirement

# Getter function for reconnect_needed
def is_reconnect_needed():
    global reconnect_needed
    return reconnect_needed

def is_connected():
    """
    Check if the Meshtastic device is connected.
    Returns True if connected, False otherwise.
    """
    if meshtastic_client is None:
        return False

    if isinstance(meshtastic_client, meshtastic.serial_interface.SerialInterface):
        # For serial connections, check if the serial port is open
        return meshtastic_client.interface.is_open()

    elif isinstance(meshtastic_client, meshtastic.tcp_interface.TCPInterface):
        # For network connections, check if the socket is connected
        return meshtastic_client.is_connected()

    else:
        # Unknown connection type
        logger.error("Unknown Meshtastic connection type.")
        return False

async def check_connection():
    global reconnect_needed
    while True:
        if not is_connected():  # Assuming 'is_connected' is a method that checks the connection
            if not reconnect_needed:
                logger.warning("Connection lost, marking for reconnection...")
                reconnect_needed = True
        await asyncio.sleep(30)  # Check every 30 seconds

def on_lost_meshtastic_connection(interface):
    global reconnect_needed, is_initial_connection, meshtastic_client
    if not reconnect_needed:
        logger.error("Lost connection. Marking for reconnection...")
        reconnect_needed = True
        is_initial_connection = False
        if meshtastic_client:
            try:
                meshtastic_client.close()  # Close the connection gracefully
            except Exception as e:
                logger.error(f"Error closing Meshtastic connection: {e}")
            meshtastic_client = None

async def reconnect_meshtastic():
    global meshtastic_client, reconnect_needed
    attempts = 0
    max_attempts = 5
    backoff_factor = 2

    while not meshtastic_client and reconnect_needed and attempts < max_attempts:
        attempts += 1
        delay = min(5 * backoff_factor ** (attempts - 1), 60)  # Exponential backoff with a max delay
        logger.info(f"Reconnecting to Meshtastic (Attempt {attempts})...")
        meshtastic_client = connect_meshtastic()

        if meshtastic_client:
            logger.info("Reconnected to Meshtastic successfully.")
            reconnect_needed = False
        else:
            logger.error(f"Reconnection attempt #{attempts} failed. Retrying in {delay} secs...")
            await asyncio.sleep(delay)

            
is_initial_connection = True  # Flag to indicate if it's the initial connection attempt

def connect_meshtastic():
    global meshtastic_client, is_initial_connection
    try:
        connection_type = relay_config["meshtastic"]["connection_type"]
        target = relay_config["meshtastic"]["serial_port"] if connection_type == "serial" else relay_config["meshtastic"]["host"]

        logger.info(f"Attempting to connect to Meshtastic {connection_type} {target}...")

        if connection_type == "serial":
            meshtastic_client = meshtastic.serial_interface.SerialInterface(target)
        else:
            meshtastic_client = meshtastic.tcp_interface.TCPInterface(hostname=target)

        logger.info(f"Connected to Meshtastic {connection_type} {target}.")
        is_initial_connection = False
        return meshtastic_client
    except Exception as e:
        logger.error(f"Error establishing Meshtastic connection to {connection_type} {target}: {e}")
        return None


# Callback for new messages from Meshtastic
def on_meshtastic_message(packet, loop=None):
    from matrix_utils import matrix_relay

    sender = packet["fromId"]

    if "text" in packet["decoded"] and packet["decoded"]["text"]:
        text = packet["decoded"]["text"]

        if "channel" in packet:
            channel = packet["channel"]
        else:
            if packet["decoded"]["portnum"] == "TEXT_MESSAGE_APP":
                channel = 0
            else:
                logger.debug(f"Unknown packet")
                return

        # Check if the channel is mapped to a Matrix room in the configuration
        channel_mapped = False
        for room in matrix_rooms:
            if room["meshtastic_channel"] == channel:
                channel_mapped = True
                break

        if not channel_mapped:
            logger.debug(f"Skipping message from unmapped channel {channel}")
            return

        logger.info(
            f"Processing inbound radio message from {sender} on channel {channel}"
        )

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

        logger.info(
            f"Relaying Meshtastic message from {longname} to Matrix: {formatted_message}"
        )

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
        portnum = packet["decoded"]["portnum"]

        plugins = load_plugins()
        found_matching_plugin = False
        for plugin in plugins:
            if not found_matching_plugin:
                result = asyncio.run_coroutine_threadsafe(
                    plugin.handle_meshtastic_message(
                        packet, formatted_message=None, longname=None, meshnet_name=None
                    ),
                    loop=loop,
                )
                found_matching_plugin = result.result()
                if found_matching_plugin:
                    logger.debug(
                        f"Processed {portnum} with plugin {plugin.plugin_name}"
                    )
