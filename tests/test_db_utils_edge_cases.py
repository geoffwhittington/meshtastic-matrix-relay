#!/usr/bin/env python3
"""
Test suite for Database utilities edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- Database connection failures
- Corrupted database handling
- Concurrent access issues
- File permission errors
- Database migration edge cases
- Transaction rollback scenarios
- Memory constraints and large datasets
"""

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


class TestDBUtilsEdgeCases(unittest.TestCase):
    """Test cases for Database utilities edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Clear any cached database path
        clear_db_path_cache()
        # Reset global config
        import mmrelay.db_utils

        mmrelay.db_utils.config = None

    def tearDown(self):
        """Clean up after each test method."""
        clear_db_path_cache()

    def test_get_db_path_permission_error(self):
        """Test get_db_path when directory creation fails due to permissions."""
        with patch("mmrelay.db_utils.get_data_dir", return_value="/readonly/data"):
            with patch("os.makedirs", side_effect=PermissionError("Permission denied")):
                # Should still return a path even if directory creation fails
                result = get_db_path()
                self.assertIn("meshtastic.sqlite", result)

    def test_get_db_path_custom_config_invalid_path(self):
        """Test get_db_path with custom config pointing to invalid path."""
        import mmrelay.db_utils

        mmrelay.db_utils.config = {
            "database": {"path": "/nonexistent/invalid/path/db.sqlite"}
        }

        with patch("os.makedirs", side_effect=OSError("Cannot create directory")):
            # Should handle the error gracefully
            result = get_db_path()
            self.assertIsInstance(result, str)

    def test_initialize_database_connection_failure(self):
        """Test initialize_database when database connection fails."""
        with patch("sqlite3.connect", side_effect=sqlite3.Error("Connection failed")):
            with patch("mmrelay.db_utils.logger") as mock_logger:
                # Should handle connection failure gracefully
                initialize_database()
                mock_logger.error.assert_called()

    def test_initialize_database_corrupted_database(self):
        """Test initialize_database with corrupted database file."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temp_db:
            # Write invalid data to simulate corruption
            temp_db.write(b"corrupted database content")
            temp_db_path = temp_db.name

        try:
            with patch("mmrelay.db_utils.get_db_path", return_value=temp_db_path):
                with patch("mmrelay.db_utils.logger"):
                    # Should handle corrupted database
                    initialize_database()
                    # May log errors about corruption
        finally:
            os.unlink(temp_db_path)

    def test_save_longname_database_locked(self):
        """Test save_longname when database is locked."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = (
                sqlite3.OperationalError("database is locked")
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle database lock gracefully
            save_longname("test_id", "test_name")

    def test_save_shortname_constraint_violation(self):
        """Test save_shortname with database constraint violation."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = sqlite3.IntegrityError(
                "constraint violation"
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle constraint violation gracefully
            save_shortname("test_id", "test_name")

    def test_get_longname_connection_error(self):
        """Test get_longname when database connection fails."""
        with patch("sqlite3.connect", side_effect=sqlite3.Error("Connection failed")):
            result = get_longname("test_id")
            self.assertIsNone(result)

    def test_get_shortname_table_not_exists(self):
        """Test get_shortname when table doesn't exist."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = (
                sqlite3.OperationalError("no such table")
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            result = get_shortname("test_id")
            self.assertIsNone(result)

    def test_store_message_map_disk_full(self):
        """Test store_message_map when disk is full."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = (
                sqlite3.OperationalError("disk I/O error")
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle disk full error gracefully
            store_message_map("mesh_id", "matrix_id", "room_id", "text")

    def test_get_message_map_by_meshtastic_id_malformed_data(self):
        """Test get_message_map_by_meshtastic_id with malformed database data."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = mock_conn.cursor.return_value
            # Return malformed data (missing columns)
            mock_cursor.fetchone.return_value = ("incomplete_data",)
            mock_connect.return_value.__enter__.return_value = mock_conn

            result = get_message_map_by_meshtastic_id("test_id")
            # Should handle malformed data gracefully
            self.assertIsNotNone(result)

    def test_get_message_map_by_matrix_event_id_unicode_error(self):
        """Test get_message_map_by_matrix_event_id with unicode handling issues."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = mock_conn.cursor.return_value
            # Simulate unicode error
            mock_cursor.execute.side_effect = UnicodeDecodeError(
                "utf-8", b"", 0, 1, "invalid"
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            result = get_message_map_by_matrix_event_id("test_id")
            self.assertIsNone(result)

    def test_prune_message_map_large_dataset(self):
        """Test prune_message_map with very large dataset."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = mock_conn.cursor.return_value
            # Simulate large dataset by making count very high
            mock_cursor.fetchone.return_value = (1000000,)
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle large datasets
            prune_message_map(100)

    def test_wipe_message_map_transaction_rollback(self):
        """Test wipe_message_map when transaction needs to be rolled back."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = [
                None,
                sqlite3.Error("Transaction failed"),
            ]
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle transaction rollback
            wipe_message_map()

    def test_store_plugin_data_concurrent_access(self):
        """Test store_plugin_data with concurrent access issues."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = (
                sqlite3.OperationalError("database is locked")
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle concurrent access gracefully
            store_plugin_data("test_plugin", "test_node", {"key": "value"})

    def test_get_plugin_data_json_decode_error(self):
        """Test get_plugin_data when JSON decoding fails."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = mock_conn.cursor.return_value
            # Return invalid JSON
            mock_cursor.fetchone.return_value = ("invalid json {",)
            mock_connect.return_value.__enter__.return_value = mock_conn

            result = get_plugin_data("test_plugin")
            self.assertEqual(result, [])

    def test_get_plugin_data_for_node_memory_error(self):
        """Test get_plugin_data_for_node when memory is exhausted."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.fetchall.side_effect = MemoryError(
                "Out of memory"
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            result = get_plugin_data_for_node("test_plugin", "test_node")
            self.assertEqual(result, {})

    def test_delete_plugin_data_foreign_key_constraint(self):
        """Test delete_plugin_data with foreign key constraint issues."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.execute.side_effect = sqlite3.IntegrityError(
                "foreign key constraint"
            )
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle foreign key constraint gracefully
            delete_plugin_data("test_plugin", "test_node")

    def test_update_longnames_empty_nodes(self):
        """Test update_longnames with empty or None nodes."""
        # Should handle None gracefully
        update_longnames(None)

        # Should handle empty list gracefully
        update_longnames([])

    def test_update_shortnames_malformed_node_data(self):
        """Test update_shortnames with malformed node data."""
        malformed_nodes = MagicMock()
        malformed_nodes.values.return_value = [
            {"user": {}},  # Missing 'id' in user
            {"user": {"id": "test_id"}},  # Missing 'shortName'
            {"user": {"id": "test_id2", "shortName": None}},  # None shortName
        ]

        # Should handle malformed data gracefully
        update_shortnames(malformed_nodes)

    def test_database_path_caching_race_condition(self):
        """Test database path caching with potential race conditions."""
        import mmrelay.db_utils

        # Simulate race condition by clearing cache between calls
        def side_effect_clear_cache(*args, **kwargs):
            mmrelay.db_utils._cached_db_path = None
            return "/test/path/meshtastic.sqlite"

        with patch(
            "mmrelay.db_utils.get_data_dir", side_effect=side_effect_clear_cache
        ):
            path1 = get_db_path()
            path2 = get_db_path()
            # Should handle race condition gracefully
            self.assertIsInstance(path1, str)
            self.assertIsInstance(path2, str)

    def test_database_initialization_partial_failure(self):
        """Test database initialization when some tables fail to create."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = mock_conn.cursor.return_value
            # First table creation succeeds, second fails
            mock_cursor.execute.side_effect = [
                None,
                sqlite3.Error("Table creation failed"),
            ]
            mock_connect.return_value.__enter__.return_value = mock_conn

            # Should handle partial failure gracefully
            initialize_database()


if __name__ == "__main__":
    unittest.main()
