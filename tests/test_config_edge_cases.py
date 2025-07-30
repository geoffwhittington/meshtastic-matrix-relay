#!/usr/bin/env python3
"""
Test suite for Config module edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- YAML parsing errors
- File permission issues
- Invalid configuration structures
- Platform-specific path handling
- Module configuration setup edge cases
- Configuration file search priority
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.config import (
    get_app_path,
    get_config_paths,
    load_config,
    set_data_dir,
    setup_module_config,
)


class TestConfigEdgeCases(unittest.TestCase):
    """Test cases for Config module edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset global state
        import mmrelay.config
        mmrelay.config.relay_config = {}
        mmrelay.config.config_path = None
        mmrelay.config.custom_data_dir = None

    def test_get_app_path_frozen_executable(self):
        """Test get_app_path when running as a frozen executable."""
        with patch('sys.frozen', True, create=True):
            with patch('sys.executable', '/path/to/executable'):
                result = get_app_path()
                self.assertEqual(result, '/path/to')

    def test_get_app_path_normal_python(self):
        """Test get_app_path when running in normal Python environment."""
        with patch('sys.frozen', False, create=True):
            result = get_app_path()
            # Should return directory containing config.py
            self.assertTrue(result.endswith('mmrelay'))

    def test_get_config_paths_with_args(self):
        """Test get_config_paths with command line arguments."""
        mock_args = MagicMock()
        mock_args.config = '/custom/path/config.yaml'
        
        paths = get_config_paths(mock_args)
        self.assertEqual(paths[0], '/custom/path/config.yaml')

    def test_get_config_paths_windows_platform(self):
        """Test get_config_paths on Windows platform."""
        with patch('sys.platform', 'win32'):
            with patch('platformdirs.user_config_dir') as mock_user_config:
                mock_user_config.return_value = 'C:\\Users\\Test\\AppData\\Local\\mmrelay'
                paths = get_config_paths()
                self.assertIn('C:\\Users\\Test\\AppData\\Local\\mmrelay\\config.yaml', paths)

    def test_get_config_paths_darwin_platform(self):
        """Test get_config_paths on macOS platform."""
        with patch('sys.platform', 'darwin'):
            with patch('mmrelay.config.get_base_dir') as mock_get_base_dir:
                mock_get_base_dir.return_value = '/Users/test/.mmrelay'
                paths = get_config_paths()
                self.assertIn('/Users/test/.mmrelay/config.yaml', paths)

    def test_load_config_yaml_parse_error(self):
        """Test load_config behavior with YAML parsing errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('invalid: yaml: content: [')
            temp_path = f.name
        
        try:
            with patch('mmrelay.config.logger') as mock_logger:
                config = load_config(config_file=temp_path)
                # Should return empty config on YAML error
                self.assertEqual(config, {})
        finally:
            os.unlink(temp_path)

    def test_load_config_file_permission_error(self):
        """Test load_config behavior with file permission errors."""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with patch('os.path.isfile', return_value=True):
                with patch('mmrelay.config.logger') as mock_logger:
                    config = load_config(config_file='test.yaml')
                    # Should return empty config on permission error
                    self.assertEqual(config, {})

    def test_load_config_file_not_found_error(self):
        """Test load_config behavior with file not found errors."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with patch('os.path.isfile', return_value=True):
                with patch('mmrelay.config.logger') as mock_logger:
                    config = load_config(config_file='nonexistent.yaml')
                    # Should return empty config on file not found
                    self.assertEqual(config, {})

    def test_load_config_empty_file(self):
        """Test load_config behavior with empty configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('')  # Empty file
            temp_path = f.name
        
        try:
            config = load_config(config_file=temp_path)
            # Should handle empty file gracefully
            self.assertIsNone(config)
        finally:
            os.unlink(temp_path)

    def test_load_config_null_yaml(self):
        """Test load_config behavior with YAML file containing only null."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('null')
            temp_path = f.name
        
        try:
            config = load_config(config_file=temp_path)
            # Should handle null YAML gracefully
            self.assertIsNone(config)
        finally:
            os.unlink(temp_path)

    def test_load_config_search_priority(self):
        """Test that load_config respects search priority order."""
        with patch('mmrelay.config.get_config_paths') as mock_get_paths:
            mock_get_paths.return_value = [
                '/first/config.yaml',
                '/second/config.yaml',
                '/third/config.yaml'
            ]
            
            # Mock only the second file exists
            def mock_isfile(path):
                return path == '/second/config.yaml'
            
            with patch('os.path.isfile', side_effect=mock_isfile):
                with patch('builtins.open', mock_open(read_data='test: value')):
                    with patch('yaml.load', return_value={'test': 'value'}):
                        config = load_config()
                        self.assertEqual(config, {'test': 'value'})

    def test_setup_module_config_matrix_utils(self):
        """Test setup_module_config with matrix_utils module."""
        mock_module = MagicMock()
        mock_module.__name__ = 'mmrelay.matrix_utils'
        mock_module.matrix_homeserver = None
        
        config = {
            'matrix': {
                'homeserver': 'https://test.matrix.org',
                'access_token': 'test_token',
                'bot_user_id': '@test:matrix.org'
            },
            'matrix_rooms': [{'id': '!test:matrix.org'}]
        }
        
        result = setup_module_config(mock_module, config)
        
        self.assertEqual(mock_module.config, config)
        self.assertEqual(mock_module.matrix_homeserver, 'https://test.matrix.org')
        self.assertEqual(result, config)

    def test_setup_module_config_meshtastic_utils(self):
        """Test setup_module_config with meshtastic_utils module."""
        mock_module = MagicMock()
        mock_module.__name__ = 'mmrelay.meshtastic_utils'
        mock_module.matrix_rooms = None
        
        config = {
            'matrix_rooms': [{'id': '!test:matrix.org', 'meshtastic_channel': 0}]
        }
        
        result = setup_module_config(mock_module, config)
        
        self.assertEqual(mock_module.config, config)
        self.assertEqual(mock_module.matrix_rooms, config['matrix_rooms'])
        self.assertEqual(result, config)

    def test_setup_module_config_with_legacy_setup_function(self):
        """Test setup_module_config with module that has legacy setup_config function."""
        mock_module = MagicMock()
        mock_module.__name__ = 'test_module'
        mock_module.setup_config = MagicMock()
        
        config = {'test': 'value'}
        
        result = setup_module_config(mock_module, config)
        
        self.assertEqual(mock_module.config, config)
        mock_module.setup_config.assert_called_once()
        self.assertEqual(result, config)

    def test_setup_module_config_without_required_attributes(self):
        """Test setup_module_config with module missing expected attributes."""
        mock_module = MagicMock()
        mock_module.__name__ = 'mmrelay.matrix_utils'
        # Remove the matrix_homeserver attribute
        del mock_module.matrix_homeserver
        
        config = {
            'matrix': {
                'homeserver': 'https://test.matrix.org',
                'access_token': 'test_token',
                'bot_user_id': '@test:matrix.org'
            }
        }
        
        # Should not raise an exception
        result = setup_module_config(mock_module, config)
        self.assertEqual(result, config)

    def test_set_data_dir_with_valid_path(self):
        """Test set_data_dir with a valid directory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            set_data_dir(temp_dir)
            
            import mmrelay.config
            self.assertEqual(mmrelay.config.custom_data_dir, temp_dir)

    def test_set_data_dir_with_nonexistent_path(self):
        """Test set_data_dir with a non-existent directory path."""
        nonexistent_path = '/nonexistent/directory'
        
        # Should not raise an exception
        set_data_dir(nonexistent_path)
        
        import mmrelay.config
        self.assertEqual(mmrelay.config.custom_data_dir, nonexistent_path)

    def test_load_config_no_files_found(self):
        """Test load_config when no configuration files are found."""
        with patch('mmrelay.config.get_config_paths') as mock_get_paths:
            mock_get_paths.return_value = ['/nonexistent1.yaml', '/nonexistent2.yaml']
            
            with patch('os.path.isfile', return_value=False):
                with patch('mmrelay.config.logger') as mock_logger:
                    config = load_config()
                    
                    # Should return empty config
                    self.assertEqual(config, {})
                    
                    # Should log error messages
                    mock_logger.error.assert_called()


if __name__ == "__main__":
    unittest.main()
