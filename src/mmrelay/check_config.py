#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import yaml
from yaml.loader import SafeLoader
import platformdirs

# Define custom base directory for Unix systems
APP_NAME = "mmrelay"
APP_AUTHOR = None  # No author directory

def get_base_dir():
    """Returns the base directory for all application files."""
    if sys.platform in ["linux", "darwin"]:
        # Use ~/.mmrelay for Linux and Mac
        return os.path.expanduser(os.path.join("~", "." + APP_NAME))
    else:
        # Use platformdirs default for Windows
        return platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)

def get_config_paths():
    """
    Get a list of possible configuration file paths.
    
    Returns:
        list: A list of possible configuration file paths
    """
    # Get the base directory
    base_dir = get_base_dir()
    
    # Define possible config paths in order of preference
    config_paths = [
        # First check if a config file was specified via command line
        None,  # This will be replaced with args.config if provided
        
        # Then check in the base directory
        os.path.join(base_dir, "config.yaml"),
        
        # Then check in the current directory
        os.path.join(os.getcwd(), "config.yaml"),
        
        # Finally check in the legacy location
        os.path.join(os.getcwd(), "config", "config.yaml"),
    ]
    
    # Filter out None values
    return [path for path in config_paths if path is not None]

def main():
    """
    Check if the configuration file is valid.
    
    Returns:
        int: 0 if the configuration is valid, 1 otherwise.
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
                    return 1
                
                # Check matrix section
                if "matrix" not in config:
                    print("Error: Missing 'matrix' section in config")
                    return 1
                
                matrix_section = config["matrix"]
                required_matrix_fields = ["homeserver", "access_token", "bot_user_id"]
                missing_matrix_fields = [field for field in required_matrix_fields if field not in matrix_section]
                
                if missing_matrix_fields:
                    print(f"Error: Missing required fields in 'matrix' section: {', '.join(missing_matrix_fields)}")
                    return 1
                
                # Check matrix_rooms section
                if "matrix_rooms" not in config or not config["matrix_rooms"]:
                    print("Error: Missing or empty 'matrix_rooms' section in config")
                    return 1
                
                if not isinstance(config["matrix_rooms"], list):
                    print("Error: 'matrix_rooms' must be a list")
                    return 1
                
                for i, room in enumerate(config["matrix_rooms"]):
                    if not isinstance(room, dict):
                        print(f"Error: Room {i+1} in 'matrix_rooms' must be a dictionary")
                        return 1
                    
                    if "id" not in room:
                        print(f"Error: Room {i+1} in 'matrix_rooms' is missing the 'id' field")
                        return 1
                
                # Check meshtastic section
                if "meshtastic" not in config:
                    print("Error: Missing 'meshtastic' section in config")
                    return 1
                
                meshtastic_section = config["meshtastic"]
                if "connection_type" not in meshtastic_section:
                    print("Error: Missing 'connection_type' in 'meshtastic' section")
                    return 1
                
                connection_type = meshtastic_section["connection_type"]
                if connection_type not in ["tcp", "serial", "ble", "network"]:
                    print(f"Error: Invalid 'connection_type': {connection_type}. Must be 'tcp', 'serial', or 'ble'")
                    return 1
                
                # Check connection-specific fields
                if connection_type == "serial" and "serial_port" not in meshtastic_section:
                    print("Error: Missing 'serial_port' for 'serial' connection type")
                    return 1
                
                if connection_type in ["tcp", "network"] and "host" not in meshtastic_section:
                    print("Error: Missing 'host' for 'tcp' connection type")
                    return 1
                
                if connection_type == "ble" and "ble_address" not in meshtastic_section:
                    print("Error: Missing 'ble_address' for 'ble' connection type")
                    return 1
                
                print("Configuration file is valid!")
                return 0
            except yaml.YAMLError as e:
                print(f"Error parsing YAML in {config_path}: {e}")
                return 1
            except Exception as e:
                print(f"Error checking configuration: {e}")
                return 1
    
    print("Error: No configuration file found in any of the following locations:")
    for path in config_paths:
        print(f"  - {path}")
    print("\nRun 'mmrelay --generate-config' to generate a sample configuration file.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
