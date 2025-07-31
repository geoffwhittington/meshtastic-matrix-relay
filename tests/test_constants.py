"""
Test suite for constants validation.

This module tests that all constants are properly defined, have valid values,
and maintain logical relationships with each other.
"""

import pytest
from mmrelay.constants import (
    app,
    config,
    database,
    formats,
    messages,
    network,
    queue,
)


class TestConstantsValidity:
    """Test that all constants are properly defined and valid."""

    def test_config_keys_are_strings(self):
        """All config keys must be non-empty strings."""
        config_keys = [
            getattr(config, attr)
            for attr in dir(config)
            if attr.startswith("CONFIG_KEY_")
        ]
        assert len(config_keys) >= 20  # We have 39 defined
        for key in config_keys:
            assert isinstance(key, str)
            assert len(key) > 0
            assert key.strip() == key  # No leading/trailing whitespace

    def test_config_sections_are_strings(self):
        """All config sections must be non-empty strings."""
        config_sections = [
            getattr(config, attr)
            for attr in dir(config)
            if attr.startswith("CONFIG_SECTION_")
        ]
        assert len(config_sections) >= 5  # We have multiple sections
        for section in config_sections:
            assert isinstance(section, str)
            assert len(section) > 0
            assert section.strip() == section

    def test_connection_types_consistency(self):
        """Connection types must be valid and consistent."""
        types = [
            network.CONNECTION_TYPE_TCP,
            network.CONNECTION_TYPE_SERIAL,
            network.CONNECTION_TYPE_BLE,
            network.CONNECTION_TYPE_NETWORK,
        ]

        # All should be strings
        for conn_type in types:
            assert isinstance(conn_type, str)
            assert len(conn_type) > 0

        # No duplicates except network (legacy alias)
        unique_types = set(types)
        assert len(unique_types) >= 3  # tcp, serial, ble (network may be alias)

        # Network should be alias for tcp (legacy support)
        assert network.CONNECTION_TYPE_NETWORK in ["tcp", "network"]

    def test_queue_constants_relationships(self):
        """Queue constants must have logical relationships."""
        assert queue.QUEUE_HIGH_WATER_MARK < queue.MAX_QUEUE_SIZE
        assert queue.QUEUE_MEDIUM_WATER_MARK < queue.QUEUE_HIGH_WATER_MARK
        assert queue.QUEUE_LOG_THRESHOLD >= 1
        assert queue.DEFAULT_MESSAGE_DELAY >= network.MINIMUM_MESSAGE_DELAY

        # Water marks should be reasonable percentages
        high_percentage = queue.QUEUE_HIGH_WATER_MARK / queue.MAX_QUEUE_SIZE
        medium_percentage = queue.QUEUE_MEDIUM_WATER_MARK / queue.MAX_QUEUE_SIZE
        assert 0.5 <= high_percentage <= 0.9  # 50-90%
        assert 0.3 <= medium_percentage <= 0.7  # 30-70%

    def test_database_limits_reasonable(self):
        """Database limits should be reasonable values."""
        assert 10 <= database.DEFAULT_MSGS_TO_KEEP <= 10000
        assert 10 <= database.DEFAULT_MAX_DATA_ROWS_PER_NODE_BASE <= 1000
        assert database.DEFAULT_TEXT_TRUNCATION_LENGTH >= 10
        assert database.DEFAULT_DISTANCE_KM_FALLBACK > 0
        assert database.DEFAULT_RADIUS_KM > 0
        assert database.PROGRESS_TOTAL_STEPS > 0
        assert database.PROGRESS_COMPLETE <= database.PROGRESS_TOTAL_STEPS

    def test_app_metadata_valid(self):
        """App metadata should be properly formatted."""
        assert isinstance(app.APP_NAME, str)
        assert len(app.APP_NAME) > 0
        assert isinstance(app.APP_DISPLAY_NAME, str)
        assert len(app.APP_DISPLAY_NAME) > 0
        assert app.WINDOWS_PLATFORM == "win32"

    def test_format_constants_valid(self):
        """Message format constants should be valid."""
        assert isinstance(formats.DEFAULT_MESHTASTIC_PREFIX, str)
        assert isinstance(formats.DEFAULT_MATRIX_PREFIX, str)
        assert len(formats.DEFAULT_MESHTASTIC_PREFIX) > 0
        assert len(formats.DEFAULT_MATRIX_PREFIX) > 0

        # Should contain format placeholders
        assert "{" in formats.DEFAULT_MESHTASTIC_PREFIX
        assert "{" in formats.DEFAULT_MATRIX_PREFIX

    def test_network_timeouts_reasonable(self):
        """Network timeout constants should be reasonable."""
        assert network.DEFAULT_BACKOFF_TIME > 0
        assert network.MINIMUM_MESSAGE_DELAY >= 0
        assert network.MILLISECONDS_PER_SECOND == 1000
        assert network.ERRNO_BAD_FILE_DESCRIPTOR == 9

    def test_message_constants_valid(self):
        """Message constants should be valid."""
        assert messages.DEFAULT_LOG_SIZE_MB > 0
        assert messages.DEFAULT_LOG_BACKUP_COUNT >= 0
        assert messages.LOG_SIZE_BYTES_MULTIPLIER == 1024 * 1024
        assert messages.PORTNUM_NUMERIC_VALUE >= 0
        assert messages.DEFAULT_CHANNEL_VALUE >= 0

        # EMOJI_FLAG_VALUE is in formats module, not messages
        assert formats.EMOJI_FLAG_VALUE >= 0


class TestConstantsImports:
    """Test that constants can be imported correctly."""

    def test_constants_package_imports(self):
        """Test that all constants modules can be imported."""
        # These should not raise ImportError
        from mmrelay.constants import app  # noqa: F401
        from mmrelay.constants import config  # noqa: F401
        from mmrelay.constants import database  # noqa: F401
        from mmrelay.constants import formats  # noqa: F401
        from mmrelay.constants import messages  # noqa: F401
        from mmrelay.constants import network  # noqa: F401
        from mmrelay.constants import queue  # noqa: F401

    def test_common_constants_available_from_init(self):
        """Test that commonly used constants are re-exported from __init__.py."""
        from mmrelay.constants import (  # noqa: F401
            APP_NAME,
            CONFIG_SECTION_MATRIX,
            CONFIG_SECTION_MESHTASTIC,
            DEFAULT_MESSAGE_DELAY,
            MAX_QUEUE_SIZE,
            DEFAULT_MESHTASTIC_PREFIX,
            DEFAULT_MATRIX_PREFIX,
        )

    def test_constants_used_in_codebase_are_accessible(self):
        """Test that constants actually used in the codebase are accessible."""
        # Test a sampling of constants that are imported in the main codebase
        from mmrelay.constants.config import CONFIG_SECTION_MATRIX
        from mmrelay.constants.network import CONNECTION_TYPE_TCP
        from mmrelay.constants.queue import DEFAULT_MESSAGE_DELAY
        from mmrelay.constants.formats import TEXT_MESSAGE_APP

        assert isinstance(CONFIG_SECTION_MATRIX, str)
        assert isinstance(CONNECTION_TYPE_TCP, str)
        assert isinstance(DEFAULT_MESSAGE_DELAY, (int, float))
        assert isinstance(TEXT_MESSAGE_APP, (int, str))


class TestConstantsConsistency:
    """Test consistency between related constants."""

    def test_config_keys_match_expected_patterns(self):
        """Config keys should follow consistent naming patterns."""
        config_keys = [
            attr
            for attr in dir(config)
            if attr.startswith("CONFIG_KEY_") and not attr.startswith("__")
        ]

        for key_name in config_keys:
            key_value = getattr(config, key_name)
            # Key values should be lowercase with underscores
            assert key_value.islower() or "_" in key_value

    def test_connection_types_used_consistently(self):
        """Connection types should be used consistently across modules."""
        # Test that connection types are defined and used consistently
        tcp_type = network.CONNECTION_TYPE_TCP
        serial_type = network.CONNECTION_TYPE_SERIAL
        ble_type = network.CONNECTION_TYPE_BLE

        # Should be lowercase
        assert tcp_type.islower()
        assert serial_type.islower()
        assert ble_type.islower()

        # Should be single words or common abbreviations
        assert tcp_type in ["tcp", "network"]
        assert serial_type == "serial"
        assert ble_type == "ble"

    def test_queue_size_calculations_correct(self):
        """Queue size calculations should be mathematically correct."""
        # Test that water marks are calculated as percentages
        max_size = queue.MAX_QUEUE_SIZE
        high_mark = queue.QUEUE_HIGH_WATER_MARK
        medium_mark = queue.QUEUE_MEDIUM_WATER_MARK

        # Should be calculated as percentages (allowing for int conversion)
        expected_high = int(max_size * 0.75)
        expected_medium = int(max_size * 0.50)

        assert high_mark == expected_high
        assert medium_mark == expected_medium

    def test_default_values_are_sensible(self):
        """Default values should be sensible for production use."""
        # Message delay should be at least the firmware minimum
        assert queue.DEFAULT_MESSAGE_DELAY >= network.MINIMUM_MESSAGE_DELAY

        # Queue size should be reasonable for memory usage
        assert 100 <= queue.MAX_QUEUE_SIZE <= 10000

        # Database retention should be reasonable
        assert 50 <= database.DEFAULT_MSGS_TO_KEEP <= 5000

        # Log size should be reasonable
        assert 1 <= messages.DEFAULT_LOG_SIZE_MB <= 100
