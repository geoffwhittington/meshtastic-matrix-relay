import asyncio
import time
import logging
import re
import sqlite3
import yaml
import meshtastic.tcp_interface
import meshtastic.serial_interface
from nio import AsyncClient, AsyncClientConfig, MatrixRoom, RoomMessageText
from pubsub import pub
from yaml.loader import SafeLoader

bot_start_time = int(time.time() * 1000)

logging.basicConfig()
logger = logging.getLogger(name="meshtastic.matrix.relay")

# Load configuration
with open("config.yaml", "r") as f:
    relay_config = yaml.load(f, Loader=SafeLoader)

logger.setLevel(getattr(logging, relay_config["logging"]["level"].upper()))

# Initialize SQLite database
def initialize_database():
    with sqlite3.connect("meshtastic.sqlite") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS longnames (meshtastic_id TEXT PRIMARY KEY, longname TEXT)"
        )
        conn.commit()


# Get the longname for a given Meshtastic ID
def get_longname(meshtastic_id):
    with sqlite3.connect("meshtastic.sqlite") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT longname FROM longnames WHERE meshtastic_id=?", (meshtastic_id,)
        )
        result = cursor.fetchone()
    return result[0] if result else None


def save_longname(meshtastic_id, longname):
    with sqlite3.connect("meshtastic.sqlite") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO longnames (meshtastic_id, longname) VALUES (?, ?)",
            (meshtastic_id, longname),
        )
        conn.commit()


def update_longnames():
    if meshtastic_interface.nodes:
        for node in meshtastic_interface.nodes.values():
            user = node.get("user")
            if user:
                meshtastic_id = user["id"]
                longname = user.get("longName", "N/A")
                save_longname(meshtastic_id, longname)


# Initialize Meshtastic interface
connection_type = relay_config["meshtastic"]["connection_type"]
if connection_type == "serial":
    serial_port = relay_config["meshtastic"]["serial_port"]
    logger.info(f"Connecting to radio using serial port {serial_port} ...")
    meshtastic_interface = meshtastic.serial_interface.SerialInterface(serial_port)
else:
    target_host = relay_config["meshtastic"]["host"]
    logger.info(f"Connecting to radio at {target_host} ...")
    meshtastic_interface = meshtastic.tcp_interface.TCPInterface(hostname=target_host)

matrix_client = None

# Matrix configuration
matrix_homeserver = relay_config["matrix"]["homeserver"]
matrix_access_token = relay_config["matrix"]["access_token"]
bot_user_id = relay_config["matrix"]["bot_user_id"]
matrix_room_id = relay_config["matrix"]["room_id"]

# Send message to the Matrix room
async def matrix_relay(matrix_client, message, longname, meshnet_name):
    try:
        content = {
            "msgtype": "m.text",
            "body": message,
            "meshtastic_longname": longname,
            "meshtastic_meshnet": meshnet_name,
        }
        await asyncio.wait_for(
            matrix_client.room_send(
                room_id=matrix_room_id,
                message_type="m.room.message",
                content=content,
            ),
            timeout=0.5,
        )
        logger.info(f"Sent inbound radio message to matrix room: {matrix_room_id}")

    except asyncio.TimeoutError:
        logger.error(f"Timed out while waiting for Matrix response")
    except Exception as e:
        logger.error(f"Error sending radio message to matrix room {matrix_room_id}: {e}")

# Callback for new messages from Meshtastic
def on_meshtastic_message(packet, loop=None):
    sender = packet["fromId"]

    if "text" in packet["decoded"] and packet["decoded"]["text"]:
        text = packet["decoded"]["text"]

        # Check if the channel is in the packet and if it matches the specified channel
        if 'channel' in packet:
            if packet['channel'] == relay_config["meshtastic"]["channel"]:
                logger.info(f"Processing inbound radio message from {sender}")

                longname = get_longname(sender) or sender
                meshnet_name = relay_config["meshtastic"]["meshnet_name"]

                formatted_message = f"[{longname}/{meshnet_name}]: {text}"

                asyncio.run_coroutine_threadsafe(
                    matrix_relay(matrix_client, formatted_message, longname, meshnet_name),
                    loop=loop,
                )
            else:
                logger.info(f"Skipping message from channel {packet['channel']} (sender: {sender})")
        else:
            logger.debug(f"Unknown packet")


def truncate_message(text, max_bytes=234):  #234 is the maximum that we can run without an error. Trying it for awhile, otherwise lower this to 230 or less.
    """
    Truncate the given text to fit within the specified byte size.

    :param text: The text to truncate.
    :param max_bytes: The maximum allowed byte size for the truncated text.
    :return: The truncated text.
    """
    truncated_text = text.encode('utf-8')[:max_bytes].decode('utf-8', 'ignore')
    return truncated_text



# Callback for new messages in Matrix room
async def on_room_message(room: MatrixRoom, event: RoomMessageText) -> None:
    
    full_display_name = "Unknown user"
    if room.room_id == matrix_room_id and event.sender != bot_user_id:
        message_timestamp = event.server_timestamp

        if message_timestamp > bot_start_time:
            text = event.body.strip()
            
            # Remove unnecessary part of the message content
            split_content = text.split("]: ", 1)
            if len(split_content) > 1:
                text = split_content[1]

            logger.info(f"Processing matrix message from {event.sender}: {text}")

            longname = event.source['content'].get("meshtastic_longname")
            meshnet_name = event.source['content'].get("meshtastic_meshnet")
            local_meshnet_name = relay_config["meshtastic"]["meshnet_name"]

            if longname and meshnet_name:
                if meshnet_name != local_meshnet_name:
                    short_longname = longname[:3]
                    short_meshnet_name = meshnet_name[:4]
                    text = f"{short_longname}/{short_meshnet_name}: {text}"
                else:
                    logger.info("Ignoring message from the same meshnet.")
                    return
            else:
                display_name_response = await matrix_client.get_displayname(event.sender)
                full_display_name = display_name_response.displayname or event.sender
                short_display_name = full_display_name[:5]

                text = f"{short_display_name}[M]: {text}"

            text = truncate_message(text)

            if relay_config["meshtastic"]["broadcast_enabled"]:
                logger.info(f"Sending radio message from {full_display_name} to radio broadcast")
                meshtastic_interface.sendText(
                    text=text, channelIndex=relay_config["meshtastic"]["channel"]
                )
            else:
                logger.debug(f"Broadcast not supported: Message from {full_display_name} dropped.")


async def main():
    global matrix_client

    # Initialize the SQLite database
    initialize_database()

    config = AsyncClientConfig(encryption_enabled=False)
    matrix_client = AsyncClient(matrix_homeserver, bot_user_id, config=config)
    matrix_client.access_token = matrix_access_token

    # Register the Meshtastic message callback
    logger.info(f"Listening for inbound radio messages ...")
    pub.subscribe(
        on_meshtastic_message, "meshtastic.receive", loop=asyncio.get_event_loop()
    )

    # Register the message callback
    logger.info(f"Listening for inbound matrix messages ...")
    matrix_client.add_event_callback(on_room_message, RoomMessageText)

    # Start the Matrix client
    while True:
        # Update longnames
        update_longnames()

        await matrix_client.sync_forever(timeout=30000)
        await asyncio.sleep(60)  # Update longnames every 60 seconds

asyncio.run(main())