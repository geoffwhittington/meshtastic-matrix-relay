#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import yaml
from yaml.loader import SafeLoader


def get_config_paths():
    """
    Get a list of possible configuration file paths.

    Returns:
        list: A list of possible configuration file paths
    """
    from mmrelay.config import get_config_paths as get_paths

    return get_paths()


def check_config():
    """
    Check if the configuration file is valid.

    Returns:
        bool: True if the configuration is valid, False otherwise.
    """
    config_paths = get_config_paths()
    config_path = None

    # Try each config path in order until we find one that exists
    for path in config_paths:
        if os.path.isfile(path):
            config_path = path
            print(f"Found configuration file at: {config_path}")
            try:
                with open(config_path, "r") as f:
                    config = yaml.load(f, Loader=SafeLoader)

                # Check if config is empty
                if not config:
                    print("Error: Configuration file is empty or invalid")
                    return False

                # Check matrix section
                if "matrix" not in config:
                    print("Error: Missing 'matrix' section in config")
                    return False

                matrix_section = config["matrix"]
                required_matrix_fields = ["homeserver", "access_token", "bot_user_id"]
                missing_matrix_fields = [
                    field
                    for field in required_matrix_fields
                    if field not in matrix_section
                ]

                if missing_matrix_fields:
                    print(
                        f"Error: Missing required fields in 'matrix' section: {', '.join(missing_matrix_fields)}"
                    )
                    return False

                # Check matrix_rooms section
                if "matrix_rooms" not in config or not config["matrix_rooms"]:
                    print("Error: Missing or empty 'matrix_rooms' section in config")
                    return False

                if not isinstance(config["matrix_rooms"], list):
                    print("Error: 'matrix_rooms' must be a list")
                    return False

                for i, room in enumerate(config["matrix_rooms"]):
                    if not isinstance(room, dict):
                        print(
                            f"Error: Room {i+1} in 'matrix_rooms' must be a dictionary"
                        )
                        return False

                    if "id" not in room:
                        print(
                            f"Error: Room {i+1} in 'matrix_rooms' is missing the 'id' field"
                        )
                        return False

                # Check meshtastic section
                if "meshtastic" not in config:
                    print("Error: Missing 'meshtastic' section in config")
                    return False

                meshtastic_section = config["meshtastic"]
                if "connection_type" not in meshtastic_section:
                    print("Error: Missing 'connection_type' in 'meshtastic' section")
                    return False

                connection_type = meshtastic_section["connection_type"]
                if connection_type not in ["tcp", "serial", "ble"]:
                    print(
                        f"Error: Invalid 'connection_type': {connection_type}. Must be 'tcp', 'serial', or 'ble'"
                    )
                    return False

                # Check connection-specific fields
                if (
                    connection_type == "serial"
                    and "serial_port" not in meshtastic_section
                ):
                    print("Error: Missing 'serial_port' for 'serial' connection type")
                    return False

                if connection_type == "tcp" and "host" not in meshtastic_section:
                    print("Error: Missing 'host' for 'tcp' connection type")
                    return False

                if connection_type == "ble" and "ble_address" not in meshtastic_section:
                    print("Error: Missing 'ble_address' for 'ble' connection type")
                    return False

                print("Configuration file is valid!")
                return True
            except yaml.YAMLError as e:
                print(f"Error parsing YAML in {config_path}: {e}")
                return False
            except Exception as e:
                print(f"Error checking configuration: {e}")
                return False

    print("Error: No configuration file found in any of the following locations:")
    for path in config_paths:
        print(f"  - {path}")
    print("\nRun 'mmrelay --generate-config' to generate a sample configuration file.")
    return False
