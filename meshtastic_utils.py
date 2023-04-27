import logging
import meshtastic.tcp_interface
import meshtastic.serial_interface

from config import relay_config

logger = logging.getLogger(name="M<>M Relay.Meshtastic")
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
