import asyncio
import threading
import json
import sqlite3
import logging
import yaml
import re
import meshtastic.tcp_interface
import meshtastic.serial_interface
from nio import AsyncClient, AsyncClientConfig, MatrixRoom, RoomMessageText, RoomMessage
from pubsub import pub
from meshtastic import mesh_pb2
from yaml.loader import SafeLoader

logging.basicConfig()
logger = logging.getLogger(name="meshtastic.matrix.relay")

# Collect configuration
relay_config = None
with open("config.yaml", "r") as f:
    relay_config = yaml.load(f, Loader=SafeLoader)

if relay_config["logging"]["level"] == "debug":
    logger.setLevel(logging.DEBUG)
elif relay_config["logging"]["level"] == "info":
    logger.setLevel(logging.INFO)
elif relay_config["logging"]["level"] == "warn":
    logger.setLevel(logging.WARN)
elif relay_config["logging"]["level"] == "error":
    logger.setLevel(logging.ERROR)


# Connect to the Meshtastic device
logger.info(f"Starting Meshtastic <==> Matrix Relay...")

# Add a new configuration option to select between serial and network connections
connection_type = relay_config["meshtastic"]["connection_type"]

if connection_type == "serial":
    serial_port = relay_config["meshtastic"]["serial_port"]
    logger.info(f"Connecting to radio using serial port {serial_port} ...")
    meshtastic_interface = meshtastic.serial_interface.SerialInterface(serial_port)
    logger.info(f"Connected to radio using serial port {serial_port}.")
else:
    target_host = relay_config["meshtastic"]["host"]
    logger.info(f"Connecting to radio at {target_host} ...")
    meshtastic_interface = meshtastic.tcp_interface.TCPInterface(hostname=target_host)
    logger.info(f"Connected to radio at {target_host}.")

matrix_client = None

# Matrix configuration
matrix_homeserver = relay_config["matrix"]["homeserver"]
matrix_access_token = relay_config["matrix"]["access_token"]
bot_user_id = relay_config["matrix"]["bot_user_id"]
matrix_room_id = relay_config["matrix"]["room_id"]

# SQLite configuration
db_file = "meshtastic.sqlite"
db = sqlite3.connect(db_file)

# Initialize the database
db.execute("CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, longname TEXT)")
db.execute(
    "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender_id TEXT, text TEXT, timestamp INTEGER)"
)
db.commit()


# Function to insert or update a node
def upsert_node(id, longname):
    db.execute(
        "INSERT OR REPLACE INTO nodes (id, longname) VALUES (?, ?)", (id, longname)
    )
    db.commit()


# Function to insert a message
def insert_message(sender_id, text, timestamp):
    db.execute(
        "INSERT INTO messages (sender_id, text, timestamp) VALUES (?, ?, ?)",
        (sender_id, text, timestamp),
    )
    db.commit()


# Function to get the node's longname
def get_node_longname(sender):
    cursor = db.cursor()
    cursor.execute("SELECT longname FROM nodes WHERE id = ?", (sender,))
    row = cursor.fetchone()
    return row[0] if row else sender


async def matrix_relay(matrix_client, message):
    try:
        await asyncio.wait_for(
            matrix_client.room_send(
                room_id=matrix_room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": message},
            ),
            timeout=0.5,
        )
        logger.info(f"Sent inbound radio message to matrix room: {matrix_room_id}")

    except asyncio.TimeoutError:
        logger.error(
            f"Timed out while waiting for Matrix response - room {matrix_room_id}: {e}"
        )
    except Exception as e:
        logger.error(
            f"Error sending radio message to matrix room {matrix_room_id}: {e}"
        )


# Callback for new messages from Meshtastic
def on_meshtastic_message(packet, loop=None):
    global matrix_client
    sender = packet["fromId"]

    if "text" in packet["decoded"] and packet["decoded"]["text"]:
        text = packet["decoded"]["text"]
        # timestamp = packet["received"]

        if logger.level == logging.DEBUG:
            logger.debug(f"Processing radio message from {sender}: {text}")
        elif logger.level == logging.INFO:
            logger.info(f"Processing inbound radio message from {sender}")

        formatted_message = f"{sender}: {text}"
        # create an event loop
        asyncio.run_coroutine_threadsafe(
            matrix_relay(matrix_client, formatted_message),
            loop=loop,
        )

        # insert_message(sender, text, timestamp)


# Callback for new messages in Matrix room
async def on_room_message(room: MatrixRoom, event: RoomMessageText) -> None:
    logger.info(
        f"Detected inbound matrix message from {event.sender} in room {room.room_id}"
    )

    if room.room_id == matrix_room_id and event.sender != bot_user_id:
        target_node = None

        if event.formatted_body:
            text = event.formatted_body.strip()
        else:
            text = event.body.strip()

        logger.debug(f"Processing matrix message from {event.sender}: {text}")

        # Opportunistically detect node in message text !124abcd:
        match = re.search(r"(![\da-z]+):", text)
        if match:
            target_node = match.group(1)

        text = re.sub(r"<mx-reply>.*?</mx-reply>", "", text)
        text = f"{event.source['sender']}: {text}"
        text = text[0:80]

        if target_node:
            logger.debug(
                f"Sending radio message from {event.sender} to {target_node} ..."
            )
            meshtastic_interface.sendText(
                text=text,
                channelIndex=relay_config["meshtastic"]["channel"],
                destinationId=target_node,
            )
            logger.info(f"Sent radio message from {event.sender} to {target_node}")
        elif relay_config["meshtastic"]["broadcast_enabled"]:
            logger.debug(
                f"Sending radio message from {event.sender} to radio broadcast ..."
            )
            meshtastic_interface.sendText(
                text=text, channelIndex=relay_config["meshtastic"]["channel"]
            )
            logger.info(f"Sent radio message from {event.sender} to radio broadcast")
        elif not relay_config["meshtastic"]["broadcast_enabled"]:
            logger.debug(
                f"Broadcast not supported: Message from {event.sender} dropped."
            )


async def main():
    global matrix_client

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
    await matrix_client.sync_forever(timeout=30000)


asyncio.run(main())
