#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
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

def main():
    """
    Main function for the check-config command.
    
    Returns:
        int: 0 if the configuration is valid, 1 otherwise.
    """
    if check_config():
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
