import logging
import os
from config import relay_config

def get_logger(name):
    logger = logging.getLogger(name=name)
    log_level = getattr(logging, relay_config["logging"]["level"].upper())
    logger.setLevel(log_level)
    logger.propagate = False

    # Add stream handler (console logging)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S %z",
        )
    )
    logger.addHandler(stream_handler)

    # Check if file logging is enabled
    if relay_config["logging"].get("log_to_file", False):
        # Default to `mmrelay.log` if no filename is provided
        log_file = relay_config["logging"].get("filename", "mmrelay.log")

        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S %z",
            )
        )
        logger.addHandler(file_handler)

    return logger
