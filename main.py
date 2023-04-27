"""
This script connects a Meshtastic mesh network to Matrix chat rooms by relaying messages between them.
It uses Meshtastic-python and Matrix nio client library to interface with the radio and the Matrix server respectively.
"""
import asyncio
import logging
from nio import (
    RoomMessageText,
    RoomMessageNotice,
)
from pubsub import pub
from typing import List, Union
from db_utils import initialize_database, get_longname, update_longnames
from matrix_utils import connect_matrix, matrix_relay, join_matrix_room, on_room_message
from plugin_loader import load_plugins

from config import relay_config
from meshtastic_utils import connect_meshtastic, on_meshtastic_message

# Configure logging
logger = logging.getLogger(name="M<>M Relay")
log_level = getattr(logging, relay_config["logging"]["level"].upper())


logger.setLevel(log_level)
logger.propagate = False  # Add this line to prevent double logging

handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(
        fmt=f"%(asctime)s %(levelname)s:%(name)s:%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %z",
    )
)
logger.addHandler(handler)


meshtastic_interface = connect_meshtastic()
matrix_rooms: List[dict] = relay_config["matrix_rooms"]
matrix_access_token = relay_config["matrix"]["access_token"]


async def main():
    # Initialize the SQLite database
    initialize_database()

    matrix_client = await connect_matrix()

    logger.info("Connecting to Matrix server...")
    try:
        login_response = await matrix_client.login(matrix_access_token)
        logger.info(f"Login response: {login_response}")
    except Exception as e:
        logger.error(f"Error connecting to Matrix server: {e}")
        return

    # Join the rooms specified in the config.yaml
    for room in matrix_rooms:
        await join_matrix_room(matrix_client, room["id"])

    # Register the Meshtastic message callback
    logger.info(f"Listening for inbound radio messages ...")
    pub.subscribe(
        on_meshtastic_message, "meshtastic.receive", loop=asyncio.get_event_loop()
    )

    # Register the message callback
    logger.info(f"Listening for inbound matrix messages ...")
    matrix_client.add_event_callback(
        on_room_message, (RoomMessageText, RoomMessageNotice)
    )

    # Start the Matrix client
    while True:
        try:
            # Update longnames
            update_longnames(meshtastic_interface.nodes)

            logger.info("Syncing with Matrix server...")
            await matrix_client.sync_forever(timeout=30000)
            logger.info("Sync completed.")
        except Exception as e:
            logger.error(f"Error syncing with Matrix server: {e}")

        await asyncio.sleep(60)  # Update longnames every 60 seconds


asyncio.run(main())
