#!/usr/bin/env python3
"""
Test suite for the MMRelay configuration checker.

Tests the configuration validation functionality including:
- Configuration file discovery
- YAML parsing and validation
- Required field validation
- Connection type validation
- Error handling and reporting
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, mock_open

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.config_checker import check_config, get_config_paths


class TestConfigChecker(unittest.TestCase):
    """Test cases for the configuration checker."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [
                {"id": "!room1:matrix.org", "meshtastic_channel": 0}
            ],
            "meshtastic": {
                "connection_type": "tcp",
                "host": "192.168.1.100"
            }
        }

    def test_get_config_paths(self):
        """Test that get_config_paths returns a list of paths."""
        with patch('mmrelay.config.get_config_paths') as mock_get_paths:
            mock_get_paths.return_value = ['/path1/config.yaml', '/path2/config.yaml']
            
            paths = get_config_paths()
            
            self.assertIsInstance(paths, list)
            self.assertEqual(len(paths), 2)
            mock_get_paths.assert_called_once()

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_valid_tcp(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test configuration validation with valid TCP configuration."""
        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = self.valid_config
        
        result = check_config()
        
        self.assertTrue(result)
        mock_print.assert_any_call("Found configuration file at: /test/config.yaml")
        mock_print.assert_any_call("Configuration file is valid!")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_valid_serial(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test configuration validation with valid serial configuration."""
        serial_config = self.valid_config.copy()
        serial_config["meshtastic"] = {
            "connection_type": "serial",
            "serial_port": "/dev/ttyUSB0"
        }
        
        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = serial_config
        
        result = check_config()
        
        self.assertTrue(result)
        mock_print.assert_any_call("Configuration file is valid!")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_valid_ble(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test configuration validation with valid BLE configuration."""
        ble_config = self.valid_config.copy()
        ble_config["meshtastic"] = {
            "connection_type": "ble",
            "ble_address": "AA:BB:CC:DD:EE:FF"
        }
        
        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = ble_config
        
        result = check_config()
        
        self.assertTrue(result)
        mock_print.assert_any_call("Configuration file is valid!")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.print')
    def test_check_config_no_file_found(self, mock_print, mock_isfile, mock_get_paths):
        """Test behavior when no configuration file is found."""
        mock_get_paths.return_value = ['/test/config.yaml', '/test2/config.yaml']
        mock_isfile.return_value = False
        
        result = check_config()
        
        self.assertFalse(result)
        mock_print.assert_any_call("Error: No configuration file found in any of the following locations:")
        mock_print.assert_any_call("  - /test/config.yaml")
        mock_print.assert_any_call("  - /test2/config.yaml")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_empty_config(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with empty configuration."""
        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = None
        
        result = check_config()
        
        self.assertFalse(result)
        mock_print.assert_any_call("Error: Configuration file is empty or invalid")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_matrix_section(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing matrix section."""
        invalid_config = {"meshtastic": {"connection_type": "tcp"}}

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing 'matrix' section in config")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_matrix_fields(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing required matrix fields."""
        invalid_config = {
            "matrix": {"homeserver": "https://matrix.org"},  # Missing access_token and bot_user_id
            "matrix_rooms": [{"id": "!room1:matrix.org"}],
            "meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing required fields in 'matrix' section: access_token, bot_user_id")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_matrix_rooms(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing matrix_rooms section."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing or empty 'matrix_rooms' section in config")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_invalid_matrix_rooms_type(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with invalid matrix_rooms type."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": "not_a_list",  # Should be a list
            "meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: 'matrix_rooms' must be a list")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_invalid_room_format(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with invalid room format in matrix_rooms."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": ["not_a_dict"],  # Should be dict objects
            "meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Room 1 in 'matrix_rooms' must be a dictionary")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_room_id(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing room id in matrix_rooms."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"meshtastic_channel": 0}],  # Missing 'id' field
            "meshtastic": {"connection_type": "tcp", "host": "192.168.1.100"}
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Room 1 in 'matrix_rooms' is missing the 'id' field")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_meshtastic_section(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing meshtastic section."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"id": "!room1:matrix.org"}]
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing 'meshtastic' section in config")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_connection_type(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing connection_type in meshtastic section."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"id": "!room1:matrix.org"}],
            "meshtastic": {"host": "192.168.1.100"}  # Missing connection_type
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing 'connection_type' in 'meshtastic' section")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_invalid_connection_type(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with invalid connection_type."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"id": "!room1:matrix.org"}],
            "meshtastic": {"connection_type": "invalid_type"}
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Invalid 'connection_type': invalid_type. Must be 'tcp', 'serial', or 'ble'")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_serial_port(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing serial_port for serial connection."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"id": "!room1:matrix.org"}],
            "meshtastic": {"connection_type": "serial"}  # Missing serial_port
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing 'serial_port' for 'serial' connection type")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_tcp_host(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing host for TCP connection."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"id": "!room1:matrix.org"}],
            "meshtastic": {"connection_type": "tcp"}  # Missing host
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing 'host' for 'tcp' connection type")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_missing_ble_address(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with missing ble_address for BLE connection."""
        invalid_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [{"id": "!room1:matrix.org"}],
            "meshtastic": {"connection_type": "ble"}  # Missing ble_address
        }

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.return_value = invalid_config

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error: Missing 'ble_address' for 'ble' connection type")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_yaml_error(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with YAML parsing error."""
        from yaml import YAMLError

        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.side_effect = YAMLError("Invalid YAML syntax")

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error parsing YAML in /test/config.yaml: Invalid YAML syntax")

    @patch('mmrelay.config_checker.get_config_paths')
    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    @patch('builtins.print')
    def test_check_config_general_exception(self, mock_print, mock_yaml_load, mock_file, mock_isfile, mock_get_paths):
        """Test behavior with general exception during config checking."""
        mock_get_paths.return_value = ['/test/config.yaml']
        mock_isfile.return_value = True
        mock_yaml_load.side_effect = Exception("General error")

        result = check_config()

        self.assertFalse(result)
        mock_print.assert_any_call("Error checking configuration: General error")


if __name__ == "__main__":
    unittest.main()
