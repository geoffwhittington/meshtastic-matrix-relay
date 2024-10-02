"""
This script connects a Meshtastic mesh network to Matrix chat rooms by relaying messages between them.
It uses Meshtastic-python and Matrix nio client library to interface with the radio and the Matrix server respectively.
"""
import asyncio
import signal
from nio import (
    RoomMessageText,
    RoomMessageNotice,
)
from pubsub import pub
from typing import List
from db_utils import initialize_database, update_longnames, update_shortnames
from matrix_utils import (
    connect_matrix,
    join_matrix_room,
    on_room_message,
    logger as matrix_logger,
)
from plugin_loader import load_plugins
from config import relay_config
from log_utils import get_logger

# Import meshtastic_utils as a module to set event_loop
import meshtastic_utils
from meshtastic_utils import (
    connect_meshtastic,
    on_meshtastic_message,
    on_lost_meshtastic_connection,
    logger as meshtastic_logger,
)

# Initialize logger
logger = get_logger(name="M<>M Relay")

# Extract Matrix configuration
matrix_rooms: List[dict] = relay_config["matrix_rooms"]
matrix_access_token = relay_config["matrix"]["access_token"]

async def main():
    """
    Main asynchronous function to set up and run the relay.
    """
    # Set the event loop in meshtastic_utils
    meshtastic_utils.event_loop = asyncio.get_event_loop()

    # Initialize the SQLite database
    initialize_database()

    # Load plugins early
    load_plugins()

    # Connect to Meshtastic
    meshtastic_utils.meshtastic_client = connect_meshtastic()

    # Connect to Matrix
    matrix_client = await connect_matrix()

    matrix_logger.info("Connecting to Matrix...")
    try:
        await matrix_client.login(matrix_access_token)
    except Exception as e:
        matrix_logger.error(f"Error connecting to Matrix server: {e}")
        return

    # Join the rooms specified in the config.yaml
    for room in matrix_rooms:
        await join_matrix_room(matrix_client, room["id"])

    # Register the message callback for Matrix
    matrix_logger.info("Listening for inbound Matrix messages...")
    matrix_client.add_event_callback(
        on_room_message, (RoomMessageText, RoomMessageNotice)
    )

    # Set up shutdown event and signal handlers
    shutdown_event = asyncio.Event()

    def shutdown():
        matrix_logger.info("Shutdown signal received. Closing down...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

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
                await asyncio.wait(
                    [sync_task, shutdown_event.wait()],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if shutdown_event.is_set():
                    matrix_logger.info("Shutdown event detected. Stopping sync loop...")
                    sync_task.cancel()
                    await sync_task
                    break
            except Exception as e:
                matrix_logger.error(f"Error syncing with Matrix server: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    finally:
        # Cleanup
        matrix_logger.info("Closing Matrix client...")
        await matrix_client.close()
        if meshtastic_utils.meshtastic_client:
            meshtastic_logger.info("Closing Meshtastic client...")
            meshtastic_utils.meshtastic_client.close()
        # Cancel any remaining tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        matrix_logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
