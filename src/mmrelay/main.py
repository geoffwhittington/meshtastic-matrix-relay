"""
This script connects a Meshtastic mesh network to Matrix chat rooms by relaying messages between them.
It uses Meshtastic-python and Matrix nio client library to interface with the radio and the Matrix server respectively.
"""

import asyncio
import logging
import signal
import sys

from nio import ReactionEvent, RoomMessageEmote, RoomMessageNotice, RoomMessageText

# Import meshtastic_utils as a module to set event_loop
from mmrelay import meshtastic_utils
from mmrelay.db_utils import (
    initialize_database,
    update_longnames,
    update_shortnames,
    wipe_message_map,
)
from mmrelay.log_utils import get_logger
from mmrelay.matrix_utils import connect_matrix, join_matrix_room
from mmrelay.matrix_utils import logger as matrix_logger
from mmrelay.matrix_utils import on_room_message
from mmrelay.meshtastic_utils import connect_meshtastic
from mmrelay.meshtastic_utils import logger as meshtastic_logger
from mmrelay.plugin_loader import load_plugins

# Initialize logger
logger = get_logger(name="M<>M Relay")

# Set the logging level for 'nio' to ERROR to suppress warnings
logging.getLogger("nio").setLevel(logging.ERROR)


async def main(config):
    """
    Main asynchronous function to set up and run the relay.
    Includes logic for wiping the message_map if configured in database.msg_map.wipe_on_restart
    or db.msg_map.wipe_on_restart (legacy format).
    Also updates longnames and shortnames periodically as before.

    Args:
        config: The loaded configuration
    """
    # Extract Matrix configuration
    from typing import List

    matrix_rooms: List[dict] = config["matrix_rooms"]

    # Set the event loop in meshtastic_utils
    meshtastic_utils.event_loop = asyncio.get_event_loop()

    # Initialize the SQLite database
    initialize_database()

    # Check database config for wipe_on_restart (preferred format)
    database_config = config.get("database", {})
    msg_map_config = database_config.get("msg_map", {})
    wipe_on_restart = msg_map_config.get("wipe_on_restart", False)

    # If not found in database config, check legacy db config
    if not wipe_on_restart:
        db_config = config.get("db", {})
        legacy_msg_map_config = db_config.get("msg_map", {})
        legacy_wipe_on_restart = legacy_msg_map_config.get("wipe_on_restart", False)

        if legacy_wipe_on_restart:
            wipe_on_restart = legacy_wipe_on_restart
            logger.warning(
                "Using 'db.msg_map' configuration (legacy). 'database.msg_map' is now the preferred format and 'db.msg_map' will be deprecated in a future version."
            )

    if wipe_on_restart:
        logger.debug("wipe_on_restart enabled. Wiping message_map now (startup).")
        wipe_message_map()

    # Load plugins early
    load_plugins(passed_config=config)

    # Connect to Meshtastic
    meshtastic_utils.meshtastic_client = connect_meshtastic(passed_config=config)

    # Connect to Matrix
    matrix_client = await connect_matrix(passed_config=config)

    # Join the rooms specified in the config.yaml
    for room in matrix_rooms:
        await join_matrix_room(matrix_client, room["id"])

    # Register the message callback for Matrix
    matrix_logger.info("Listening for inbound Matrix messages...")
    matrix_client.add_event_callback(
        on_room_message, (RoomMessageText, RoomMessageNotice, RoomMessageEmote)
    )
    # Add ReactionEvent callback so we can handle matrix reactions
    matrix_client.add_event_callback(on_room_message, ReactionEvent)

    # Set up shutdown event
    shutdown_event = asyncio.Event()

    async def shutdown():
        matrix_logger.info("Shutdown signal received. Closing down...")
        meshtastic_utils.shutting_down = True  # Set the shutting_down flag
        shutdown_event.set()

    loop = asyncio.get_running_loop()

    # Handle signals differently based on the platform
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    else:
        # On Windows, we can't use add_signal_handler, so we'll handle KeyboardInterrupt
        pass

    # -------------------------------------------------------------------
    # IMPORTANT: We create a task to run the meshtastic_utils.check_connection()
    # so its while loop runs in parallel with the matrix sync loop
    # Use "_" to avoid trunk's "assigned but unused variable" warning
    # -------------------------------------------------------------------
    _ = asyncio.create_task(meshtastic_utils.check_connection())

    # Start the Matrix client sync loop
    try:
        while not shutdown_event.is_set():
            try:
                if meshtastic_utils.meshtastic_client:
                    # Update longnames & shortnames
                    update_longnames(meshtastic_utils.meshtastic_client.nodes)
                    update_shortnames(meshtastic_utils.meshtastic_client.nodes)
                else:
                    meshtastic_logger.warning("Meshtastic client is not connected.")

                matrix_logger.info("Starting Matrix sync loop...")
                sync_task = asyncio.create_task(
                    matrix_client.sync_forever(timeout=30000)
                )

                shutdown_task = asyncio.create_task(shutdown_event.wait())

                # Wait for either the matrix sync to fail, or for a shutdown
                done, pending = await asyncio.wait(
                    [sync_task, shutdown_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if shutdown_event.is_set():
                    matrix_logger.info("Shutdown event detected. Stopping sync loop...")
                    sync_task.cancel()
                    try:
                        await sync_task
                    except asyncio.CancelledError:
                        pass
                    break

            except Exception as e:
                if shutdown_event.is_set():
                    break
                matrix_logger.error(f"Error syncing with Matrix server: {e}")
                await asyncio.sleep(5)  # Wait briefly before retrying
    except KeyboardInterrupt:
        await shutdown()
    finally:
        # Cleanup
        matrix_logger.info("Closing Matrix client...")
        await matrix_client.close()
        if meshtastic_utils.meshtastic_client:
            meshtastic_logger.info("Closing Meshtastic client...")
            try:
                meshtastic_utils.meshtastic_client.close()
            except Exception as e:
                meshtastic_logger.warning(f"Error closing Meshtastic client: {e}")

        # Attempt to wipe message_map on shutdown if enabled
        if wipe_on_restart:
            logger.debug("wipe_on_restart enabled. Wiping message_map now (shutdown).")
            wipe_message_map()

        # Cancel the reconnect task if it exists
        if meshtastic_utils.reconnect_task:
            meshtastic_utils.reconnect_task.cancel()
            meshtastic_logger.info("Cancelled Meshtastic reconnect task.")

        # Cancel any remaining tasks (including the check_conn_task)
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        matrix_logger.info("Shutdown complete.")


def run_main(args):
    """Run the main functionality of the application.

    Args:
        args: The parsed command-line arguments

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # Run the main functionality

    # Load configuration
    from mmrelay.config import load_config

    # Load configuration with args
    config = load_config(args=args)

    # Set the global config variables in each module
    from mmrelay import meshtastic_utils, matrix_utils, plugin_loader, log_utils, db_utils
    from mmrelay.plugins import base_plugin
    meshtastic_utils.config = config
    matrix_utils.config = config
    plugin_loader.config = config
    log_utils.config = config
    db_utils.config = config
    base_plugin.config = config

    # Check if config exists and has the required keys
    required_keys = ["matrix", "meshtastic", "matrix_rooms"]
    logger.info(f"Checking for required keys in config: {required_keys}")
    logger.info(f"Config keys: {list(config.keys()) if config else 'None'}")

    # Check each key individually for better debugging
    for key in required_keys:
        if key not in config:
            logger.error(f"Required key '{key}' is missing from config")

    if not config or not all(key in config for key in required_keys):
        # Exit with error if no config exists
        missing_keys = [key for key in required_keys if key not in config]
        logger.error(
            f"Configuration is missing required keys: {missing_keys}. "
            "Please create a valid config.yaml file or use --generate-config to create one."
        )
        return 1

    try:
        asyncio.run(main(config))
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
        return 0
    except Exception as e:
        logger.error(f"Error running main functionality: {e}")
        return 1


if __name__ == "__main__":
    import sys

    from mmrelay.cli import main

    sys.exit(main())
