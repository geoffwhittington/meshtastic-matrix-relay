#!/usr/bin/env python3
"""
Generate docker-compose.yml based on sample_config.yaml
This ensures consistency between configuration and Docker setup.
"""

import yaml
import os
import sys
from pathlib import Path

def load_sample_config():
    """Load the sample configuration file."""
    config_path = Path("src/mmrelay/tools/sample_config.yaml")
    if not config_path.exists():
        print(f"Error: {config_path} not found")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def generate_docker_compose(config):
    """Generate docker-compose.yml based on configuration."""
    
    # Base docker-compose structure
    compose = {
        'version': '3.8',
        'services': {
            'mmrelay': {
                'build': '.',
                'container_name': 'meshtastic-matrix-relay',
                'restart': 'unless-stopped',
                'environment': [
                    'TZ=UTC',
                    'PYTHONUNBUFFERED=1'
                ],
                'volumes': [
                    './config.yaml:/app/config/config.yaml:ro',
                    'mmrelay_data:/app/data',
                    'mmrelay_logs:/app/logs'
                ],
                'healthcheck': {
                    'test': ['CMD', 'pgrep', '-f', 'mmrelay'],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 3,
                    'start_period': '10s'
                },
                'logging': {
                    'driver': 'json-file',
                    'options': {
                        'max-size': '10m',
                        'max-file': '3'
                    }
                }
            }
        },
        'volumes': {
            'mmrelay_data': {'driver': 'local'},
            'mmrelay_logs': {'driver': 'local'}
        }
    }
    
    # Analyze meshtastic configuration
    meshtastic_config = config.get('meshtastic', {})
    connection_type = meshtastic_config.get('connection_type', 'tcp')
    
    # Configure based on connection type
    if connection_type == 'tcp':
        # TCP connections work with default network
        compose['services']['mmrelay']['network_mode'] = 'host'
        
    elif connection_type == 'serial':
        # Serial connections need device access
        compose['services']['mmrelay']['devices'] = [
            '/dev/ttyUSB0:/dev/ttyUSB0',
            '/dev/ttyACM0:/dev/ttyACM0'
        ]
        # Add comment about uncommenting the right device
        
    elif connection_type == 'ble':
        # BLE needs privileged mode or specific capabilities
        compose['services']['mmrelay']['privileged'] = True
        compose['services']['mmrelay']['network_mode'] = 'host'
    
    # Add ports if any plugins need them
    plugins_config = config.get('plugins', {})
    if plugins_config and any('web' in str(plugin).lower() for plugin in plugins_config.values() if isinstance(plugin, dict)):
        compose['services']['mmrelay']['ports'] = ['8080:8080']
    
    return compose

def write_docker_compose(compose_data, output_path="docker-compose.generated.yml"):
    """Write the docker-compose.yml file with comments."""

    # Create header comment
    header = f"""# Generated docker-compose.yml
# This file is generated from sample_config.yaml
# To regenerate: python scripts/generate-docker-compose.py
# Compare with existing docker-compose.yml and update as needed

"""

    with open(output_path, 'w') as f:
        f.write(header)
        yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"Generated {output_path}")
    print(f"💡 Compare with existing docker-compose.yml: diff docker-compose.yml {output_path}")

def add_connection_comments(output_path="docker-compose.generated.yml"):
    """Add helpful comments to the generated file."""
    
    with open(output_path, 'r') as f:
        content = f.read()
    
    # Add comments for different connection types
    comments = """
    # Connection type configuration:
    # 
    # For TCP connections (recommended):
    #   - Uses network_mode: host for easy device access
    #   - Configure meshtastic.host in config.yaml
    #
    # For Serial connections:
    #   - Uncomment and modify the devices section below
    #   - Update the device path to match your setup
    #   - devices:
    #     - /dev/ttyUSB0:/dev/ttyUSB0  # Most common
    #     - /dev/ttyACM0:/dev/ttyACM0  # Alternative
    #
    # For BLE connections:
    #   - privileged: true is required for BLE access
    #   - Alternative: use cap_add for more security
    #   - Configure meshtastic.ble_address in config.yaml
"""
    
    # Insert comments after the services section
    content = content.replace('services:', f'services:{comments}')
    
    with open(output_path, 'w') as f:
        f.write(content)

def main():
    """Main function."""
    print("Generating docker-compose.yml from sample_config.yaml...")
    
    # Load sample configuration
    config = load_sample_config()
    
    # Generate docker-compose structure
    compose_data = generate_docker_compose(config)
    
    # Write the file
    write_docker_compose(compose_data)
    
    # Add helpful comments
    add_connection_comments()
    
    print("✅ docker-compose.yml generated successfully!")
    print("💡 Edit config.yaml and run 'docker-compose up -d' to start")

if __name__ == "__main__":
    main()
