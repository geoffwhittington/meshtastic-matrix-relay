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

matrix_rooms: List[dict] = relay_config["matrix_rooms"]

logger = get_logger(name="Meshtastic")

meshtastic_client = None
reconnecting = False

def connect_meshtastic(force_connect=False):
    global meshtastic_client, reconnecting
    if meshtastic_client and not force_connect:
        return meshtastic_client

    # Ensure previous connection is closed
    if meshtastic_client:
        try:
            meshtastic_client.close()
        except Exception as e:
            logger.error(f"Error while closing previous connection: {e}")
        meshtastic_client = None

    # Initialize Meshtastic interface
    connection_type = relay_config["meshtastic"]["connection_type"]
    max_backoff = 60  # maximum backoff time in seconds
    backoff = 1       # initial backoff time in seconds

    while True:
        try:
            if connection_type == "serial":
                serial_port = relay_config["meshtastic"]["serial_port"]
                logger.info(f"Connecting to serial port {serial_port} ...")
                meshtastic_client = meshtastic.serial_interface.SerialInterface(serial_port)
            
            elif connection_type == "ble":
                ble_address = relay_config["meshtastic"].get("ble_address")
                if ble_address:
                    logger.info(f"Connecting to BLE address {ble_address} ...")
                    meshtastic_client = meshtastic.ble_interface.BLEInterface(address=ble_address)
                else:
                    logger.error("No BLE address provided.")
                    return None
            
            else:
                target_host = relay_config["meshtastic"]["host"]
                logger.info(f"Connecting to host {target_host} ...")
                meshtastic_client = meshtastic.tcp_interface.TCPInterface(hostname=target_host)

            nodeInfo = meshtastic_client.getMyNodeInfo()
            logger.info(f"Connected to {nodeInfo['user']['shortName']} / {nodeInfo['user']['hwModel']}")
            reconnecting = False
            break  # exit the retry loop on successful connection
        
        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)  # exponential backoff with a maximum limit

    return meshtastic_client

def on_lost_meshtastic_connection(interface):
    global reconnecting
    if reconnecting:
        return
    reconnecting = True
    logger.error("Lost connection. Reconnecting...")
    connect_meshtastic(force_connect=True)

def on_meshtastic_message(packet, loop=None):
    from matrix_utils import matrix_relay

    sender = packet["fromId"]

    if "text" in packet["decoded"] and packet["decoded"]["text"]:
        text = packet["decoded"]["text"]

        if "channel" in packet:
            channel = packet["channel"]
        else:
    
