import asyncio
import time
import meshtastic.tcp_interface
import meshtastic.serial_interface
from typing import List
from config import relay_config
from log_utils import get_logger
from db_utils import get_longname, get_shortname
from plugin_loader import load_plugins
from ble_interface import BLEInterface

matrix_rooms: List[dict] = relay_config["matrix_rooms"]

logger = get_logger(name="Meshtastic")

meshtastic_client = None

def connect_meshtastic(force_connect=False):
    global meshtastic_client
    if meshtastic_client and not force_connect:
        return meshtastic_client

    meshtastic_client = None

    # Initialize Meshtastic interface
    connection_type = relay_config["meshtastic"]["connection_type"]
    retry_limit = (
        relay_config["meshtastic"]["retry_limit"]
        if "retry_limit" in relay_config["meshtastic"]
        else 3
    )
    attempts = 1
    successful = False

    if connection_type == "serial":
        serial_port = relay_config["meshtastic"]["serial_port"]
        logger.info(f"Connecting to serial port {serial_port} ...")
        while not successful and attempts <= retry_limit:
            try:
                meshtastic_client = meshtastic.serial_interface.SerialInterface(
                    serial_port
                )
                successful = True
            except Exception as e:
                attempts += 1
                if attempts <= retry_limit:
                    logger.warn(
                        f"Attempt #{attempts-1} failed. Retrying in {attempts} secs {e}"
                    )
                    time.sleep(attempts)
                else:
                    logger.error(f"Could not connect: {e}")
                    return None

    elif connection_type == "ble":
        ble_address = relay_config["meshtastic"].get("ble_address")
        ble_name = relay_config["meshtastic"].get("ble_name")

        if ble_address and ble_name:
            logger.info(f"Connecting to BLE address {ble_address} ...")
        elif ble_address:
            logger.info(f"Connecting to BLE address {ble_address} ...")
        elif ble_name:
            logger.info(f"Connecting to BLE name {ble_name} ...")
        else:
            logger.error("No BLE address or name provided.")
            return None

        while not successful and attempts <= retry_limit:
            try:
                if ble_address:
                    meshtastic_client = BLEInterface(address=ble_address)
                elif ble_name:
                    meshtastic_client = BLEInterface(address=ble_name)
                successful = True
            except Exception as e:
                attempts += 1
                if attempts <= retry_limit:
                    logger.warn(
                        f"Attempt #{attempts-1} failed. Retrying in {attempts} secs {e}"
                    )
                    time.sleep(attempts)
                else:
                    logger.error(f"Could not connect: {e}")
                    return None

    else:
        target_host = relay_config["meshtastic"]["host"]
        logger.info(f"Connecting to host {target_host} ...")
        while not successful and attempts <= retry_limit:
            try:
                meshtastic_client = meshtastic.tcp_interface.TCPInterface(
                    hostname=target_host
                )
                successful = True
            except Exception as e:
                attempts += 1
                if attempts <= retry_limit:
                    logger.warn(
                        f"Attempt #{attempts-1} failed. Retrying in {attempts} secs... {e}"
                    )
                    time.sleep(attempts)
                else:
                    logger.error(f"Could not connect: {e}")
                    return None

    nodeInfo = meshtastic_client.getMyNodeInfo()
    logger.info(
        f"Connected to {nodeInfo['user']['shortName']} / {nodeInfo['user']['hwModel']}"
    )
    return meshtastic_client
