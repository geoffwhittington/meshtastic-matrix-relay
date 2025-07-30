import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.meshtastic_utils import connect_meshtastic


class TestMeshtasticUtils(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Reset global state to avoid test interference
        import mmrelay.meshtastic_utils
        mmrelay.meshtastic_utils.meshtastic_client = None
        mmrelay.meshtastic_utils.config = None

    def test_connect_meshtastic_safe_node_info_access(self):
        """Test that getMyNodeInfo access is handled safely with missing fields."""
        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        # Mock a successful connection but with missing node info fields
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = None  # Empty node info

        with patch('mmrelay.meshtastic_utils.serial_port_exists', return_value=True), \
             patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface', return_value=mock_client), \
             patch('mmrelay.meshtastic_utils.logger') as mock_logger:

            result = connect_meshtastic(passed_config=config)

            # Should handle None node info gracefully
            self.assertEqual(result, mock_client)
            mock_logger.info.assert_called_with("Connected to unknown / unknown")

    def test_connect_meshtastic_safe_node_info_partial_data(self):
        """Test safe access when node info has partial data."""
        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        # Mock a successful connection with partial node info
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {
            "user": {
                "shortName": "TestNode"
                # Missing hwModel
            }
        }

        with patch('mmrelay.meshtastic_utils.serial_port_exists', return_value=True), \
             patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface', return_value=mock_client), \
             patch('mmrelay.meshtastic_utils.logger') as mock_logger:

            result = connect_meshtastic(passed_config=config)

            # Should handle missing hwModel gracefully
            self.assertEqual(result, mock_client)
            mock_logger.info.assert_called_with("Connected to TestNode / unknown")

    def test_connect_meshtastic_safe_node_info_missing_user(self):
        """Test safe access when node info is missing user section."""
        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        # Mock a successful connection with node info missing user section
        mock_client = MagicMock()
        mock_client.getMyNodeInfo.return_value = {
            "other_field": "some_value"
            # Missing 'user' section entirely
        }

        with patch('mmrelay.meshtastic_utils.serial_port_exists', return_value=True), \
             patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface', return_value=mock_client), \
             patch('mmrelay.meshtastic_utils.logger') as mock_logger:

            result = connect_meshtastic(passed_config=config)

            # Should handle missing user section gracefully
            self.assertEqual(result, mock_client)
            mock_logger.info.assert_called_with("Connected to unknown / unknown")

    def test_connect_meshtastic_separate_exception_handling(self):
        """Test that specific connection errors are handled separately from general exceptions."""
        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        # Test BleakDBusError handling (first exception block)
        from bleak.exc import BleakDBusError
        with patch('mmrelay.meshtastic_utils.serial_port_exists', return_value=True), \
             patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface') as mock_interface, \
             patch('mmrelay.meshtastic_utils.logger') as mock_logger, \
             patch('mmrelay.meshtastic_utils.time.sleep'), \
             patch('mmrelay.meshtastic_utils.shutting_down', False):

            mock_interface.side_effect = [BleakDBusError("BLE error"), MagicMock()]
            
            result = connect_meshtastic(passed_config=config)

            # Should handle BleakDBusError in first exception block
            self.assertIsNotNone(result)
            # Should log with exponential backoff message
            warning_calls = [call for call in mock_logger.warning.call_args_list if "Retrying in" in str(call)]
            self.assertTrue(len(warning_calls) > 0)

    def test_connect_meshtastic_general_exception_handling(self):
        """Test that general exceptions are still handled in the second exception block."""
        config = {
            "meshtastic": {
                "connection_type": "serial", 
                "serial_port": "/dev/ttyUSB0"
            }
        }

        # Test general Exception handling (second exception block)
        with patch('mmrelay.meshtastic_utils.serial_port_exists', return_value=True), \
             patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface') as mock_interface, \
             patch('mmrelay.meshtastic_utils.logger') as mock_logger, \
             patch('mmrelay.meshtastic_utils.time.sleep'), \
             patch('mmrelay.meshtastic_utils.shutting_down', False):

            mock_interface.side_effect = [RuntimeError("Generic error"), MagicMock()]
            
            result = connect_meshtastic(passed_config=config)

            # Should handle general exception in second exception block
            self.assertIsNotNone(result)
            warning_calls = [call for call in mock_logger.warning.call_args_list if "Retrying in" in str(call)]
            self.assertTrue(len(warning_calls) > 0)

    def test_connect_meshtastic_shutdown_handling(self):
        """Test that shutdown state is properly checked in both exception blocks."""
        config = {
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"  
            }
        }

        with patch('mmrelay.meshtastic_utils.serial_port_exists', return_value=True), \
             patch('mmrelay.meshtastic_utils.meshtastic.serial_interface.SerialInterface') as mock_interface, \
             patch('mmrelay.meshtastic_utils.logger') as mock_logger, \
             patch('mmrelay.meshtastic_utils.shutting_down', True):  # Shutdown in progress

            mock_interface.side_effect = Exception("Connection error")
            
            result = connect_meshtastic(passed_config=config)

            # Should return None when shutting down
            self.assertIsNone(result)
            debug_calls = [call for call in mock_logger.debug.call_args_list if "Shutdown in progress" in str(call)]
            self.assertTrue(len(debug_calls) > 0)


if __name__ == "__main__":
    unittest.main()