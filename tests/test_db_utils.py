#!/usr/bin/env python3
"""
Test suite for database utilities in MMRelay.

Tests the SQLite database operations including:
- Database initialization and schema creation
- Node name storage and retrieval (longnames/shortnames)
- Plugin data storage and retrieval
- Message mapping for Matrix/Meshtastic correlation
- Database path resolution and caching
- Configuration-based database paths
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.db_utils import (
    clear_db_path_cache,
    delete_plugin_data,
    get_db_path,
    get_longname,
    get_message_map_by_matrix_event_id,
    get_message_map_by_meshtastic_id,
    get_plugin_data,
    get_plugin_data_for_node,
    get_shortname,
    initialize_database,
    prune_message_map,
    save_longname,
    save_shortname,
    store_message_map,
    store_plugin_data,
    update_longnames,
    update_shortnames,
    wipe_message_map,
)


class TestDbUtils(unittest.TestCase):
    """Test cases for database utilities."""

    def setUp(self):
        """Set up test environment with temporary database."""
        # Create a temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_meshtastic.sqlite")
        
        # Clear any cached database path
        clear_db_path_cache()
        
        # Mock the config to use our test database
        self.mock_config = {
            "database": {
                "path": self.test_db_path
            }
        }
        
        # Patch the config in db_utils
        import mmrelay.db_utils
        mmrelay.db_utils.config = self.mock_config

    def tearDown(self):
        """Clean up test environment."""
        # Clear cache after each test
        clear_db_path_cache()
        
        # Clean up temporary files
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        os.rmdir(self.test_dir)

    def test_get_db_path_with_config(self):
        """Test database path resolution with configuration."""
        path = get_db_path()
        self.assertEqual(path, self.test_db_path)

    def test_get_db_path_caching(self):
        """Test that database path is cached properly."""
        # First call should resolve and cache
        path1 = get_db_path()
        path2 = get_db_path()
        self.assertEqual(path1, path2)
        self.assertEqual(path1, self.test_db_path)

    @patch('mmrelay.db_utils.get_data_dir')
    def test_get_db_path_default(self, mock_get_data_dir):
        """Test database path resolution without configuration."""
        # Clear config to test default behavior
        import mmrelay.db_utils
        mmrelay.db_utils.config = None
        clear_db_path_cache()
        
        mock_get_data_dir.return_value = "/test/data"
        path = get_db_path()
        self.assertEqual(path, "/test/data/meshtastic.sqlite")

    def test_get_db_path_legacy_config(self):
        """Test database path resolution with legacy configuration format."""
        # Use legacy db.path format
        legacy_config = {
            "db": {
                "path": self.test_db_path
            }
        }
        
        import mmrelay.db_utils
        mmrelay.db_utils.config = legacy_config
        clear_db_path_cache()
        
        path = get_db_path()
        self.assertEqual(path, self.test_db_path)

    def test_initialize_database(self):
        """Test database initialization and schema creation."""
        initialize_database()
        
        # Verify database file was created
        self.assertTrue(os.path.exists(self.test_db_path))
        
        # Verify tables were created
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            
            # Check longnames table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='longnames'")
            self.assertIsNotNone(cursor.fetchone())
            
            # Check shortnames table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shortnames'")
            self.assertIsNotNone(cursor.fetchone())
            
            # Check plugin_data table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plugin_data'")
            self.assertIsNotNone(cursor.fetchone())
            
            # Check message_map table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message_map'")
            self.assertIsNotNone(cursor.fetchone())
            
            # Verify message_map has meshtastic_meshnet column
            cursor.execute("PRAGMA table_info(message_map)")
            columns = [row[1] for row in cursor.fetchall()]
            self.assertIn('meshtastic_meshnet', columns)

    def test_longname_operations(self):
        """Test longname storage and retrieval."""
        initialize_database()
        
        # Test saving and retrieving longname
        meshtastic_id = "!12345678"
        longname = "Test User"
        
        save_longname(meshtastic_id, longname)
        retrieved_longname = get_longname(meshtastic_id)
        
        self.assertEqual(retrieved_longname, longname)
        
        # Test non-existent longname
        non_existent = get_longname("!nonexistent")
        self.assertIsNone(non_existent)

    def test_shortname_operations(self):
        """Test shortname storage and retrieval."""
        initialize_database()
        
        # Test saving and retrieving shortname
        meshtastic_id = "!12345678"
        shortname = "TU"
        
        save_shortname(meshtastic_id, shortname)
        retrieved_shortname = get_shortname(meshtastic_id)
        
        self.assertEqual(retrieved_shortname, shortname)
        
        # Test non-existent shortname
        non_existent = get_shortname("!nonexistent")
        self.assertIsNone(non_existent)

    def test_update_longnames(self):
        """Test bulk longname updates from nodes."""
        initialize_database()
        
        # Mock nodes data
        nodes = {
            "!12345678": {
                "user": {
                    "id": "!12345678",
                    "longName": "Alice Smith"
                }
            },
            "!87654321": {
                "user": {
                    "id": "!87654321",
                    "longName": "Bob Jones"
                }
            }
        }
        
        update_longnames(nodes)
        
        # Verify longnames were stored
        self.assertEqual(get_longname("!12345678"), "Alice Smith")
        self.assertEqual(get_longname("!87654321"), "Bob Jones")

    def test_update_shortnames(self):
        """Test bulk shortname updates from nodes."""
        initialize_database()
        
        # Mock nodes data
        nodes = {
            "!12345678": {
                "user": {
                    "id": "!12345678",
                    "shortName": "AS"
                }
            },
            "!87654321": {
                "user": {
                    "id": "!87654321",
                    "shortName": "BJ"
                }
            }
        }
        
        update_shortnames(nodes)
        
        # Verify shortnames were stored
        self.assertEqual(get_shortname("!12345678"), "AS")
        self.assertEqual(get_shortname("!87654321"), "BJ")

    def test_plugin_data_operations(self):
        """Test plugin data storage and retrieval."""
        initialize_database()
        
        plugin_name = "test_plugin"
        meshtastic_id = "!12345678"
        test_data = {"temperature": 25.5, "humidity": 60}
        
        # Store plugin data
        store_plugin_data(plugin_name, meshtastic_id, test_data)
        
        # Retrieve plugin data for specific node
        retrieved_data = get_plugin_data_for_node(plugin_name, meshtastic_id)
        self.assertEqual(retrieved_data, test_data)
        
        # Retrieve all plugin data
        all_data = get_plugin_data(plugin_name)
        self.assertEqual(len(all_data), 1)
        self.assertEqual(json.loads(all_data[0][0]), test_data)
        
        # Delete plugin data
        delete_plugin_data(plugin_name, meshtastic_id)
        retrieved_after_delete = get_plugin_data_for_node(plugin_name, meshtastic_id)
        self.assertEqual(retrieved_after_delete, [])

    def test_message_map_operations(self):
        """Test message mapping storage and retrieval."""
        initialize_database()
        
        # Test data
        meshtastic_id = 12345
        matrix_event_id = "$event123:matrix.org"
        matrix_room_id = "!room123:matrix.org"
        meshtastic_text = "Hello from mesh"
        meshtastic_meshnet = "test_mesh"
        
        # Store message map
        store_message_map(
            meshtastic_id, matrix_event_id, matrix_room_id, 
            meshtastic_text, meshtastic_meshnet
        )
        
        # Retrieve by meshtastic_id
        result = get_message_map_by_meshtastic_id(meshtastic_id)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], matrix_event_id)
        self.assertEqual(result[1], matrix_room_id)
        self.assertEqual(result[2], meshtastic_text)
        self.assertEqual(result[3], meshtastic_meshnet)
        
        # Retrieve by matrix_event_id
        result = get_message_map_by_matrix_event_id(matrix_event_id)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], meshtastic_id)
        self.assertEqual(result[1], matrix_room_id)
        self.assertEqual(result[2], meshtastic_text)
        self.assertEqual(result[3], meshtastic_meshnet)

    def test_wipe_message_map(self):
        """Test wiping all message map entries."""
        initialize_database()
        
        # Add some test data
        store_message_map(1, "$event1:matrix.org", "!room:matrix.org", "test1")
        store_message_map(2, "$event2:matrix.org", "!room:matrix.org", "test2")
        
        # Verify data exists
        self.assertIsNotNone(get_message_map_by_meshtastic_id(1))
        self.assertIsNotNone(get_message_map_by_meshtastic_id(2))
        
        # Wipe message map
        wipe_message_map()
        
        # Verify data is gone
        self.assertIsNone(get_message_map_by_meshtastic_id(1))
        self.assertIsNone(get_message_map_by_meshtastic_id(2))

    def test_prune_message_map(self):
        """Test pruning old message map entries."""
        initialize_database()
        
        # Add multiple entries
        for i in range(10):
            store_message_map(
                i, f"$event{i}:matrix.org", "!room:matrix.org", f"test{i}"
            )
        
        # Prune to keep only 5 entries
        prune_message_map(5)
        
        # Verify only recent entries remain
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM message_map")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 5)
            
            # Verify the kept entries are the most recent ones
            cursor.execute("SELECT meshtastic_id FROM message_map ORDER BY rowid")
            kept_ids = [row[0] for row in cursor.fetchall()]
            self.assertEqual(kept_ids, [5, 6, 7, 8, 9])


if __name__ == "__main__":
    unittest.main()
