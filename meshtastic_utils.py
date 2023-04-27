import asyncio
import logging
import meshtastic.tcp_interface
import meshtastic.serial_interface
from typing import List

from config import relay_config
from log_utils import get_logger
from db_utils import get_longname
from plugin_loader import load_plugins

matrix_rooms: List[dict] = relay_config["matrix_rooms"]

logger = get_logger(name="Meshtastic")


meshtastic_client = None


def connect_meshtastic():
    global meshtastic_client
    if meshtastic_client:
        return meshtastic_client
    # Initialize Meshtastic interface
    connection_type = relay_config["meshtastic"]["connection_type"]
    if connection_type == "serial":
        serial_port = relay_config["meshtastic"]["serial_port"]
        logger.info(f"Connecting to radio using serial port {serial_port} ...")
        meshtastic_client = meshtastic.serial_interface.SerialInterface(serial_port)
    else:
        target_host = relay_config["meshtastic"]["host"]
        logger.info(f"Connecting to radio at {target_host} ...")
        meshtastic_client = meshtastic.tcp_interface.TCPInterface(hostname=target_host)
    return meshtastic_client


# Callback for new messages from Meshtastic
def on_meshtastic_message(packet, loop=None):
    from matrix_utils import connect_matrix, matrix_relay

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
        meshnet_name = relay_config["meshtastic"]["meshnet_name"]

        formatted_message = f"[{longname}/{meshnet_name}]: {text}"
        logger.info(
            f"Relaying Meshtastic message from {longname} to Matrix: {formatted_message}"
        )

        # Plugin functionality
        plugins = load_plugins()

        for plugin in plugins:
            asyncio.run_coroutine_threadsafe(
                plugin.handle_meshtastic_message(
                    packet, formatted_message, longname, meshnet_name
                ),
                loop=loop,
            )

        for room in matrix_rooms:
            if room["meshtastic_channel"] == channel:
                asyncio.run_coroutine_threadsafe(
                    matrix_relay(
                        room["id"],
                        formatted_message,
                        longname,
                        meshnet_name,
                    ),
                    loop=loop,
                )
    else:
        portnum = packet["decoded"]["portnum"]
        logger.debug(f"Ignoring {portnum} packet")
