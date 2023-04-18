import asyncio
import time
import logging
import re
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
        logger.error(f"Timed out while waiting for Matrix response")
    except Exception as e:
        logger.error(f"Error sending radio message to matrix room {matrix_room_id}: {e}")

# Callback for new messages from Meshtastic
def on_meshtastic_message(packet, loop=None):
    sender = packet["fromId"]

    if "text" in packet["decoded"] and packet["decoded"]["text"]:
        text = packet["decoded"]["text"]

        logger.info(f"Processing inbound radio message from {sender}")

        formatted_message = f"{sender}: {text}"
        asyncio.run_coroutine_threadsafe(
            matrix_relay(matrix_client, formatted_message),
            loop=loop,
        )

# Callback for new messages in Matrix room
async def on_room_message(room: MatrixRoom, event: RoomMessageText) -> None:
    if room.room_id == matrix_room_id and event.sender != bot_user_id:
        message_timestamp = event.server_timestamp

        # Only process messages with a timestamp greater than the bot's start time
        if message_timestamp > bot_start_time:
            text = event.body.strip()

            logger.info(f"Processing matrix message from {event.sender}: {text}")

            display_name_response = await matrix_client.get_displayname(event.sender)
            display_name = display_name_response.displayname or event.sender

            text = f"{display_name}: {text}"
            text = text[0:80]

            if relay_config["meshtastic"]["broadcast_enabled"]:
                logger.info(f"Sending radio message from {display_name} to radio broadcast")
                meshtastic_interface.sendText(
                    text=text, channelIndex=relay_config["meshtastic"]["channel"]
                )
            else:
                logger.debug(f"Broadcast not supported: Message from {display_name} dropped.")



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
