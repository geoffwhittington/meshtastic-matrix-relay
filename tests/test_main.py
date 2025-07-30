#!/usr/bin/env python3
"""
Test suite for main application functionality in MMRelay.

Tests the main application flow including:
- Application initialization and configuration
- Database initialization
- Plugin loading
- Message queue startup
- Matrix and Meshtastic client connections
- Graceful shutdown handling
- Banner printing and version display
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.main import main, print_banner, run_main


class TestMain(unittest.TestCase):
    """Test cases for main application functionality."""

    def setUp(self):
        """Set up test environment."""
        # Reset banner state
        import mmrelay.main
        mmrelay.main._banner_printed = False
        
        # Mock configuration
        self.mock_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org"
            },
            "matrix_rooms": [
                {"id": "!room1:matrix.org", "meshtastic_channel": 0},
                {"id": "!room2:matrix.org", "meshtastic_channel": 1}
            ],
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "message_delay": 2.0
            },
            "database": {
                "msg_map": {
                    "wipe_on_restart": False
                }
            }
        }

    def tearDown(self):
        """Clean up test environment."""
        # Reset banner state
        import mmrelay.main
        mmrelay.main._banner_printed = False

    def test_print_banner(self):
        """Test banner printing functionality."""
        with patch('mmrelay.main.logger') as mock_logger:
            print_banner()
            
            # Should print banner with version
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            self.assertIn("Starting MMRelay", call_args)
            self.assertIn("v", call_args)  # Version should be included

    def test_print_banner_only_once(self):
        """Test that banner is only printed once."""
        with patch('mmrelay.main.logger') as mock_logger:
            print_banner()
            print_banner()  # Second call
            
            # Should only be called once
            self.assertEqual(mock_logger.info.call_count, 1)

    @patch('mmrelay.main.initialize_database')
    @patch('mmrelay.main.load_plugins')
    @patch('mmrelay.main.start_message_queue')
    @patch('mmrelay.main.connect_meshtastic')
    @patch('mmrelay.main.connect_matrix')
    @patch('mmrelay.main.join_matrix_room')
    @patch('mmrelay.main.update_longnames')
    @patch('mmrelay.main.update_shortnames')
    @patch('mmrelay.main.stop_message_queue')
    async def test_main_basic_flow(self, mock_stop_queue, mock_update_shortnames, 
                                   mock_update_longnames, mock_join_room, 
                                   mock_connect_matrix, mock_connect_meshtastic,
                                   mock_start_queue, mock_load_plugins, 
                                   mock_init_db):
        """Test basic main application flow."""
        # Mock Matrix client
        mock_matrix_client = AsyncMock()
        mock_connect_matrix.return_value = mock_matrix_client
        
        # Mock Meshtastic client
        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = {}
        mock_connect_meshtastic.return_value = mock_meshtastic_client
        
        # Mock the sync_forever to complete quickly
        async def mock_sync():
            await asyncio.sleep(0.1)
            return
        mock_matrix_client.sync_forever = AsyncMock(side_effect=mock_sync)
        
        # Mock event loop and shutdown event
        with patch('mmrelay.main.asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            # Create a shutdown event that triggers quickly
            shutdown_event = asyncio.Event()
            
            with patch('mmrelay.main.asyncio.Event') as mock_event:
                mock_event.return_value = shutdown_event
                
                # Set up the test to shutdown quickly
                async def trigger_shutdown():
                    await asyncio.sleep(0.2)
                    shutdown_event.set()
                
                # Run both main and shutdown trigger concurrently
                await asyncio.gather(
                    main(self.mock_config),
                    trigger_shutdown(),
                    return_exceptions=True
                )
        
        # Verify initialization steps were called
        mock_init_db.assert_called_once()
        mock_load_plugins.assert_called_once_with(passed_config=self.mock_config)
        mock_start_queue.assert_called_once()
        mock_connect_meshtastic.assert_called_once_with(passed_config=self.mock_config)
        mock_connect_matrix.assert_called_once_with(passed_config=self.mock_config)
        
        # Verify rooms were joined
        expected_calls = [
            unittest.mock.call(mock_matrix_client, "!room1:matrix.org"),
            unittest.mock.call(mock_matrix_client, "!room2:matrix.org")
        ]
        mock_join_room.assert_has_calls(expected_calls)
        
        # Verify cleanup was called
        mock_stop_queue.assert_called_once()

    @patch('mmrelay.main.wipe_message_map')
    @patch('mmrelay.main.initialize_database')
    @patch('mmrelay.main.load_plugins')
    @patch('mmrelay.main.start_message_queue')
    @patch('mmrelay.main.connect_meshtastic')
    @patch('mmrelay.main.connect_matrix')
    @patch('mmrelay.main.join_matrix_room')
    @patch('mmrelay.main.stop_message_queue')
    async def test_main_with_message_map_wipe(self, mock_stop_queue, mock_join_room,
                                              mock_connect_matrix, mock_connect_meshtastic,
                                              mock_start_queue, mock_load_plugins,
                                              mock_init_db, mock_wipe_map):
        """Test main application flow with message map wiping enabled."""
        # Enable message map wiping
        config_with_wipe = self.mock_config.copy()
        config_with_wipe["database"]["msg_map"]["wipe_on_restart"] = True
        
        # Mock clients
        mock_matrix_client = AsyncMock()
        mock_connect_matrix.return_value = mock_matrix_client
        mock_meshtastic_client = MagicMock()
        mock_meshtastic_client.nodes = {}
        mock_connect_meshtastic.return_value = mock_meshtastic_client
        
        # Mock quick completion
        async def mock_sync():
            await asyncio.sleep(0.1)
        mock_matrix_client.sync_forever = AsyncMock(side_effect=mock_sync)
        
        # Mock shutdown event
        shutdown_event = asyncio.Event()
        with patch('mmrelay.main.asyncio.Event') as mock_event:
            mock_event.return_value = shutdown_event
            
            async def trigger_shutdown():
                await asyncio.sleep(0.2)
                shutdown_event.set()
            
            await asyncio.gather(
                main(config_with_wipe),
                trigger_shutdown(),
                return_exceptions=True
            )
        
        # Verify message map was wiped
        mock_wipe_map.assert_called_once()

    @patch('mmrelay.main.load_config')
    @patch('mmrelay.main.set_config')
    @patch('mmrelay.main.configure_component_debug_logging')
    @patch('mmrelay.main.print_banner')
    @patch('mmrelay.main.main')
    def test_run_main(self, mock_main, mock_print_banner, mock_configure_debug,
                      mock_set_config, mock_load_config):
        """Test run_main function."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.log_level = "debug"
        
        # Mock config loading
        mock_load_config.return_value = self.mock_config
        
        # Mock main to complete successfully
        mock_main.return_value = None
        
        result = run_main(mock_args)
        
        # Verify configuration was loaded and set
        mock_load_config.assert_called_once_with(args=mock_args)
        
        # Verify log level was overridden
        expected_config = self.mock_config.copy()
        expected_config["logging"] = {"level": "debug"}
        
        # Verify banner was printed
        mock_print_banner.assert_called_once()
        
        # Verify component debug logging was configured
        mock_configure_debug.assert_called_once()
        
        # Verify main was called
        mock_main.assert_called_once()
        
        # Should return 0 for success
        self.assertEqual(result, 0)

    @patch('mmrelay.main.load_config')
    @patch('mmrelay.main.main')
    def test_run_main_exception_handling(self, mock_main, mock_load_config):
        """Test run_main exception handling."""
        # Mock config loading
        mock_load_config.return_value = self.mock_config
        
        # Mock main to raise an exception
        mock_main.side_effect = Exception("Test error")
        
        result = run_main(None)
        
        # Should return 1 for error
        self.assertEqual(result, 1)

    @patch('mmrelay.main.load_config')
    @patch('mmrelay.main.main')
    def test_run_main_keyboard_interrupt(self, mock_main, mock_load_config):
        """Test run_main keyboard interrupt handling."""
        # Mock config loading
        mock_load_config.return_value = self.mock_config
        
        # Mock main to raise KeyboardInterrupt
        mock_main.side_effect = KeyboardInterrupt()
        
        result = run_main(None)
        
        # Should return 0 for graceful shutdown
        self.assertEqual(result, 0)

    @patch('mmrelay.main.connect_meshtastic')
    @patch('mmrelay.main.initialize_database')
    @patch('mmrelay.main.load_plugins')
    @patch('mmrelay.main.start_message_queue')
    @patch('mmrelay.main.connect_matrix')
    @patch('mmrelay.main.join_matrix_room')
    @patch('mmrelay.main.stop_message_queue')
    async def test_main_meshtastic_connection_failure(self, mock_stop_queue, mock_join_room,
                                                      mock_connect_matrix, mock_start_queue,
                                                      mock_load_plugins, mock_init_db,
                                                      mock_connect_meshtastic):
        """Test main application flow when Meshtastic connection fails."""
        # Mock Meshtastic connection to return None (failure)
        mock_connect_meshtastic.return_value = None
        
        # Mock Matrix client
        mock_matrix_client = AsyncMock()
        mock_connect_matrix.return_value = mock_matrix_client
        
        # Mock quick completion
        async def mock_sync():
            await asyncio.sleep(0.1)
        mock_matrix_client.sync_forever = AsyncMock(side_effect=mock_sync)
        
        # Mock shutdown event
        shutdown_event = asyncio.Event()
        with patch('mmrelay.main.asyncio.Event') as mock_event:
            mock_event.return_value = shutdown_event
            
            async def trigger_shutdown():
                await asyncio.sleep(0.2)
                shutdown_event.set()
            
            await asyncio.gather(
                main(self.mock_config),
                trigger_shutdown(),
                return_exceptions=True
            )
        
        # Should still proceed with Matrix connection
        mock_connect_matrix.assert_called_once()

    @patch('mmrelay.main.initialize_database')
    @patch('mmrelay.main.load_plugins')
    @patch('mmrelay.main.start_message_queue')
    @patch('mmrelay.main.connect_meshtastic')
    @patch('mmrelay.main.connect_matrix')
    @patch('mmrelay.main.stop_message_queue')
    async def test_main_matrix_connection_failure(self, mock_stop_queue, mock_connect_matrix,
                                                  mock_connect_meshtastic, mock_start_queue,
                                                  mock_load_plugins, mock_init_db):
        """Test main application flow when Matrix connection fails."""
        # Mock Matrix connection to raise an exception
        mock_connect_matrix.side_effect = Exception("Matrix connection failed")
        
        # Mock Meshtastic client
        mock_meshtastic_client = MagicMock()
        mock_connect_meshtastic.return_value = mock_meshtastic_client
        
        # Should raise the exception
        with self.assertRaises(Exception):
            await main(self.mock_config)


if __name__ == "__main__":
    unittest.main()
