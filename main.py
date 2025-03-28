"""
This script connects a Meshtastic mesh network to Matrix chat rooms by relaying messages between them.
It uses Meshtastic-python and Matrix nio client library to interface with the radio and the Matrix server respectively.
"""

import asyncio
import logging
import signal
import sys
from typing import List

from nio import ReactionEvent, RoomMessageEmote, RoomMessageNotice, RoomMessageText
# Ensure we handle potential E2EE exceptions during sync
from nio import exceptions as NioExceptions

# Import meshtastic_utils as a module to set event_loop
import meshtastic_utils
from config import relay_config
from db_utils import (
    initialize_database,
    update_longnames,
    update_shortnames,
    wipe_message_map,
)
from log_utils import get_logger
from matrix_utils import connect_matrix, join_matrix_room
from matrix_utils import logger as matrix_logger
from matrix_utils import on_room_message
from meshtastic_utils import connect_meshtastic
from meshtastic_utils import logger as meshtastic_logger
from plugin_loader import load_plugins

# Initialize logger
logger = get_logger(name="M<>M Relay")

# Extract Matrix configuration
matrix_rooms: List[dict] = relay_config["matrix_rooms"]

# Set the logging level for 'nio' based on our config or default to WARNING
# Keep nio logs less verbose unless our main level is DEBUG
nio_log_level_str = relay_config["logging"]["level"].upper()
if nio_log_level_str == "DEBUG":
    logging.getLogger("nio").setLevel(logging.INFO) # Show some nio info on DEBUG
else:
    logging.getLogger("nio").setLevel(logging.WARNING) # Default to WARNING otherwise


async def main():
    """
    Main asynchronous function to set up and run the relay.
    Includes logic for wiping the message_map if configured in db.msg_map.wipe_on_restart.
    Also updates longnames and shortnames periodically as before.
    Connects to Matrix (potentially with E2EE) before starting sync.
    """
    # Set the event loop in meshtastic_utils early
    meshtastic_utils.event_loop = asyncio.get_event_loop()

    # Initialize the SQLite database
    initialize_database()

    # Check db config for wipe_on_restart
    db_config = relay_config.get("db", {})
    msg_map_config = db_config.get("msg_map", {})
    wipe_on_restart = msg_map_config.get("wipe_on_restart", False)

    if wipe_on_restart:
        logger.info("wipe_on_restart enabled. Wiping message_map now (startup).")
        wipe_message_map() # Wipe before connecting/syncing

    # Load plugins early (before connections, in case they need early init)
    load_plugins()

    # Connect to Meshtastic (this blocks until successful or retry limit)
    meshtastic_utils.meshtastic_client = connect_meshtastic()
    if not meshtastic_utils.meshtastic_client and not meshtastic_utils.shutting_down:
         logger.critical("Failed to connect to Meshtastic after initial attempts. Exiting.")
         # Depending on connect_meshtastic logic, it might retry indefinitely or return None.
         # If it returns None, we should exit.
         return

    # Connect to Matrix (includes potential E2EE setup)
    matrix_client = await connect_matrix()
    if matrix_client is None:
        logger.critical("Failed to connect to Matrix. Exiting.")
        # connect_matrix logs the specific error (e.g., bad token)
        return

    # Join the rooms specified in the config.yaml AFTER successful Matrix connect
    for room in matrix_rooms:
        await join_matrix_room(matrix_client, room["id"])

    # Register the message callback for Matrix
    matrix_logger.info("Registering Matrix message callbacks...")
    matrix_client.add_event_callback(
        on_room_message, (RoomMessageText, RoomMessageNotice, RoomMessageEmote)
    )
    # Add ReactionEvent callback (m.reaction)
    matrix_client.add_event_callback(on_room_message, ReactionEvent)

    # Set up shutdown event
    shutdown_event = asyncio.Event()

    async def shutdown():
        if not meshtastic_utils.shutting_down: # Prevent double shutdown logic
            matrix_logger.info("Shutdown signal received. Closing down...")
            meshtastic_utils.shutting_down = True  # Set the global shutting_down flag
            shutdown_event.set() # Signal the main loop to stop

    loop = asyncio.get_running_loop()

    # Handle signals differently based on the platform
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
            except (ValueError, RuntimeError) as e:
                 logger.warning(f"Could not set signal handler for {sig}: {e}")
                 logger.warning("Use Ctrl+C directly if needed.")

    else:
        # On Windows, rely on KeyboardInterrupt exception in main loop
        pass

    # -------------------------------------------------------------------
    # Start the Meshtastic connection checker task
    # -------------------------------------------------------------------
    check_conn_task = asyncio.create_task(meshtastic_utils.check_connection())

    # Start the Matrix client sync loop
    try:
        while not shutdown_event.is_set():
            try:
                # Update longnames & shortnames periodically from Meshtastic node list
                # Do this less frequently or on demand? For now, keep it periodic.
                if meshtastic_utils.meshtastic_client and meshtastic_utils.meshtastic_client.nodes:
                    try:
                         update_longnames(meshtastic_utils.meshtastic_client.nodes)
                         update_shortnames(meshtastic_utils.meshtastic_client.nodes)
                    except Exception as e:
                         meshtastic_logger.warning(f"Error updating node names: {e}")
                elif not meshtastic_utils.reconnecting: # Avoid warning if reconnecting
                    meshtastic_logger.warning("Meshtastic client not connected, cannot update node names.")


                matrix_logger.info("Starting Matrix sync...")
                # sync_forever handles initial sync and subsequent syncs.
                # timeout is the time between sync requests (30s default in nio)
                # request_timeout is timeout for each individual HTTP request (e.g. /sync)
                await matrix_client.sync_forever(timeout=30000, request_timeout=60000) # 30s poll, 60s request timeout

                # If sync_forever returns (e.g., due to server error), log it and loop
                # unless shutting down.
                if not shutdown_event.is_set():
                     matrix_logger.warning("Matrix sync_forever unexpectedly stopped. Will restart sync.")
                     await asyncio.sleep(5) # Wait before restarting sync

            except NioExceptions.EncryptionError as e:
                 if shutdown_event.is_set(): break
                 matrix_logger.critical(f"Fatal Matrix Encryption Error during sync: {e}", exc_info=True)
                 matrix_logger.critical("This might be due to store corruption or device key issues.")
                 matrix_logger.critical("Attempting to continue, but E2EE might be broken.")
                 await asyncio.sleep(15) # Longer wait after critical E2EE errors
            except NioExceptions.SyncError as e:
                 if shutdown_event.is_set(): break
                 matrix_logger.error(f"Matrix SyncError: {e}", exc_info=True)
                 matrix_logger.error("Check homeserver connection and configuration.")
                 await asyncio.sleep(10) # Wait before retrying sync
            except asyncio.CancelledError:
                 matrix_logger.info("Matrix sync task cancelled.")
                 # This happens during shutdown
                 break
            except Exception as e:
                if shutdown_event.is_set():
                    break # Don't log error if shutting down
                matrix_logger.error(f"Unexpected error in Matrix sync loop: {e}", exc_info=True)
                await asyncio.sleep(5) # Wait briefly before retrying

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
        await shutdown() # Trigger graceful shutdown
    finally:
        logger.info("Starting final cleanup...")

        # Ensure shutdown event is set if not already
        shutdown_event.set()

        # Close Matrix client first
        if matrix_client:
            matrix_logger.info("Closing Matrix client...")
            try:
                await matrix_client.close()
                # Save store explicitly if using E2EE
                if matrix_client.store:
                     matrix_client.store.save()
                     logger.info("Saved E2EE store.")
            except Exception as e:
                matrix_logger.warning(f"Error closing Matrix client: {e}")

        # Close Meshtastic client
        if meshtastic_utils.meshtastic_client:
            meshtastic_logger.info("Closing Meshtastic client...")
            try:
                # Use the lock to prevent race conditions if reconnect is happening
                with meshtastic_utils.meshtastic_lock:
                     if meshtastic_utils.meshtastic_client:
                          meshtastic_utils.meshtastic_client.close()
                          meshtastic_utils.meshtastic_client = None # Clear reference
            except Exception as e:
                meshtastic_logger.warning(f"Error closing Meshtastic client: {e}")

        # Attempt to wipe message_map on shutdown if enabled
        if wipe_on_restart:
            logger.info("wipe_on_restart enabled. Wiping message_map now (shutdown).")
            wipe_message_map()

        # Cancel the Meshtastic reconnect task if it's running
        if meshtastic_utils.reconnect_task and not meshtastic_utils.reconnect_task.done():
             meshtastic_logger.info("Cancelling Meshtastic reconnect task...")
             meshtastic_utils.reconnect_task.cancel()
             try:
                 await meshtastic_utils.reconnect_task # Allow cancellation to process
             except asyncio.CancelledError:
                 pass # Expected cancellation
             except Exception as e:
                 meshtastic_logger.warning(f"Error awaiting cancelled reconnect task: {e}")


        # Cancel the connection checker task
        if check_conn_task and not check_conn_task.done():
             logger.info("Cancelling Meshtastic connection checker task...")
             check_conn_task.cancel()
             try:
                 await check_conn_task
             except asyncio.CancelledError:
                 pass # Expected
             except Exception as e:
                 logger.warning(f"Error awaiting cancelled check_conn_task: {e}")


        # Optionally cancel any other remaining tasks (be cautious)
        # tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task() and not t.done()]
        # if tasks:
        #     logger.info(f"Cancelling {len(tasks)} remaining tasks...")
        #     for task in tasks:
        #         task.cancel()
        #     await asyncio.gather(*tasks, return_exceptions=True)


        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # The main function's finally block handles cleanup
        logger.info("Exiting due to KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        sys.exit(1) # Exit with error code on unhandled exception
