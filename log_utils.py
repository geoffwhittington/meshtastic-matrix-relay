import logging

from config import relay_config


def get_logger(name):
    logger = logging.getLogger(name=name)
    log_level = getattr(logging, relay_config["logging"]["level"].upper())

    logger.setLevel(log_level)
    logger.propagate = False  # Add this line to prevent double logging

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S %z",
        )
    )
    logger.addHandler(handler)
    return logger
