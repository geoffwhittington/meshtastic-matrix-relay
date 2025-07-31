#!/usr/bin/env python3
"""
Test suite for Error Boundaries and Recovery scenarios in MMRelay.

Tests error boundaries and recovery including:
- Graceful degradation under failures
- Error isolation between components
- Recovery from transient failures
- Fallback mechanisms
- Circuit breaker patterns
- Error propagation limits
- System stability under cascading failures
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.meshtastic_utils import on_meshtastic_message
from mmrelay.message_queue import MessageQueue


class TestErrorBoundaries(unittest.TestCase):
    """Test cases for error boundaries and recovery scenarios."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset global state
        self._reset_global_state()

    def tearDown(self):
        """Clean up after each test method."""
        self._reset_global_state()

    def _reset_global_state(self):
        """Reset global state across modules."""
        # Reset meshtastic_utils globals
        if "mmrelay.meshtastic_utils" in sys.modules:
            module = sys.modules["mmrelay.meshtastic_utils"]
            module.config = None
            module.matrix_rooms = []
            module.meshtastic_client = None
            module.event_loop = None
            module.reconnecting = False
            module.shutting_down = False
            module.reconnect_task = None
            module.subscribed_to_messages = False
            module.subscribed_to_connection_lost = False

        # Reset matrix_utils globals
        if "mmrelay.matrix_utils" in sys.modules:
            module = sys.modules["mmrelay.matrix_utils"]
            if hasattr(module, "config"):
                module.config = None
            if hasattr(module, "matrix_client"):
                module.matrix_client = None

        # Reset plugin_loader globals
        if "mmrelay.plugin_loader" in sys.modules:
            module = sys.modules["mmrelay.plugin_loader"]
            if hasattr(module, "config"):
                module.config = None

    def test_plugin_failure_isolation(self):
        """Test that plugin failures don't affect other plugins or core functionality."""
        # Create plugins with different failure modes
        failing_plugin = MagicMock()
        failing_plugin.priority = 1
        failing_plugin.plugin_name = "failing_plugin"
        failing_plugin.handle_meshtastic_message = AsyncMock(
            side_effect=Exception("Plugin crashed")
        )

        working_plugin = MagicMock()
        working_plugin.priority = 5
        working_plugin.plugin_name = "working_plugin"
        working_plugin.handle_meshtastic_message = AsyncMock(return_value=False)

        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        mock_interface = MagicMock()

        with patch(
            "mmrelay.plugin_loader.load_plugins",
            return_value=[failing_plugin, working_plugin],
        ):
            with patch("mmrelay.matrix_utils.matrix_relay") as mock_matrix_relay:
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    # Set up minimal config
                    import mmrelay.meshtastic_utils

                    mmrelay.meshtastic_utils.config = {
                        "matrix_rooms": [
                            {"id": "!room:matrix.org", "meshtastic_channel": 0}
                        ]
                    }
                    mmrelay.meshtastic_utils.matrix_rooms = [
                        {"id": "!room:matrix.org", "meshtastic_channel": 0}
                    ]

                    # Process message
                    on_meshtastic_message(packet, mock_interface)

                    # Failing plugin should have been called and failed
                    failing_plugin.handle_meshtastic_message.assert_called_once()
                    mock_logger.error.assert_called()

                    # Working plugin should still have been called
                    working_plugin.handle_meshtastic_message.assert_called_once()

                    # Core functionality (Matrix relay) should still work
                    mock_matrix_relay.assert_called_once()

    def test_database_failure_graceful_degradation(self):
        """Test graceful degradation when database operations fail."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        mock_interface = MagicMock()
        mock_interface.nodes = {
            "!12345678": {
                "user": {"id": "!12345678", "longName": "Test Node", "shortName": "TN"}
            }
        }

        # Mock database failures
        with patch(
            "mmrelay.db_utils.get_longname", side_effect=Exception("Database error")
        ):
            with patch(
                "mmrelay.db_utils.get_shortname",
                side_effect=Exception("Database error"),
            ):
                with patch("mmrelay.plugin_loader.load_plugins", return_value=[]):
                    with patch(
                        "mmrelay.matrix_utils.matrix_relay"
                    ) as mock_matrix_relay:
                        with patch("mmrelay.meshtastic_utils.logger"):
                            # Set up config
                            import mmrelay.meshtastic_utils

                            mmrelay.meshtastic_utils.config = {
                                "matrix_rooms": [
                                    {"id": "!room:matrix.org", "meshtastic_channel": 0}
                                ]
                            }
                            mmrelay.meshtastic_utils.matrix_rooms = [
                                {"id": "!room:matrix.org", "meshtastic_channel": 0}
                            ]

                            # Process message
                            on_meshtastic_message(packet, mock_interface)

                            # Should still relay to Matrix despite database failures
                            mock_matrix_relay.assert_called_once()

                            # Should use fallback names from interface
                            call_args = mock_matrix_relay.call_args[0]
                            self.assertIn(
                                "Test Node", call_args[1]
                            )  # Should use interface longName

    def test_matrix_relay_failure_recovery(self):
        """Test recovery when Matrix relay fails."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
            "to": 4294967295,
            "id": 123456789,
        }

        mock_interface = MagicMock()

        # First call fails, second succeeds
        matrix_relay_calls = 0

        def matrix_relay_side_effect(*args, **kwargs):
            nonlocal matrix_relay_calls
            matrix_relay_calls += 1
            if matrix_relay_calls == 1:
                raise Exception("Matrix relay failed")
            return None

        with patch("mmrelay.plugin_loader.load_plugins", return_value=[]):
            with patch(
                "mmrelay.matrix_utils.matrix_relay",
                side_effect=matrix_relay_side_effect,
            ):
                with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                    # Set up config
                    import mmrelay.meshtastic_utils

                    mmrelay.meshtastic_utils.config = {
                        "matrix_rooms": [
                            {"id": "!room:matrix.org", "meshtastic_channel": 0}
                        ]
                    }
                    mmrelay.meshtastic_utils.matrix_rooms = [
                        {"id": "!room:matrix.org", "meshtastic_channel": 0}
                    ]

                    # Process first message (should fail)
                    on_meshtastic_message(packet, mock_interface)
                    mock_logger.error.assert_called()

                    # Process second message (should succeed)
                    mock_logger.reset_mock()
                    packet["id"] = 123456790
                    on_meshtastic_message(packet, mock_interface)

                    # Should have attempted both calls
                    self.assertEqual(matrix_relay_calls, 2)

    def test_message_queue_error_boundary(self):
        """Test message queue error boundaries and recovery."""
        queue = MessageQueue()
        queue.start(message_delay=0.1)

        success_count = 0
        failure_count = 0

        def failing_function():
            nonlocal failure_count
            failure_count += 1
            raise Exception("Function failed")

        def success_function():
            nonlocal success_count
            success_count += 1
            return MagicMock(id="success_id")

        try:
            # Queue alternating failing and successful functions
            for i in range(10):
                if i % 2 == 0:
                    queue.enqueue(failing_function, description=f"Failing function {i}")
                else:
                    queue.enqueue(success_function, description=f"Success function {i}")

            # Wait for processing
            import time

            time.sleep(2)

            # Verify that failures didn't stop successful processing
            self.assertEqual(failure_count, 5)  # 5 failing functions called
            self.assertEqual(success_count, 5)  # 5 successful functions called

        finally:
            queue.stop()

    def test_cascading_failure_prevention(self):
        """Test prevention of cascading failures across components."""
        packet = {
            "decoded": {"text": "test message", "portnum": 1},
            "fromId": "!12345678",
            "channel": 0,
        }

        mock_interface = MagicMock()

        # Create a chain of potential failures
        with patch(
            "mmrelay.db_utils.get_longname", side_effect=Exception("DB failure")
        ):
            with patch(
                "mmrelay.db_utils.get_shortname", side_effect=Exception("DB failure")
            ):
                with patch("mmrelay.plugin_loader.load_plugins") as mock_load_plugins:
                    # Plugin loading fails
                    mock_load_plugins.side_effect = Exception("Plugin loading failed")

                    with patch(
                        "mmrelay.matrix_utils.matrix_relay",
                        side_effect=Exception("Matrix failure"),
                    ):
                        with patch("mmrelay.meshtastic_utils.logger") as mock_logger:
                            # Set up config
                            import mmrelay.meshtastic_utils

                            mmrelay.meshtastic_utils.config = {
                                "matrix_rooms": [
                                    {"id": "!room:matrix.org", "meshtastic_channel": 0}
                                ]
                            }
                            mmrelay.meshtastic_utils.matrix_rooms = [
                                {"id": "!room:matrix.org", "meshtastic_channel": 0}
                            ]

                            # Process message - should not crash despite multiple failures
                            try:
                                on_meshtastic_message(packet, mock_interface)
                                # Should complete without raising exceptions
                            except Exception as e:
                                self.fail(f"Cascading failure occurred: {e}")

                            # Should have logged errors but continued processing
                            self.assertGreater(mock_logger.error.call_count, 0)

    def test_transient_failure_recovery(self):
        """Test recovery from transient failures."""
        call_count = 0

        def transient_failure_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 times
                raise Exception("Transient failure")
            return MagicMock(id="success_id")

        queue = MessageQueue()
        queue.start(message_delay=0.1)

        try:
            # Queue the same function multiple times
            for i in range(5):
                queue.enqueue(
                    transient_failure_function, description=f"Transient test {i}"
                )

            # Wait for processing
            import time

            time.sleep(1)

            # Should have attempted all calls
            self.assertEqual(call_count, 5)

        finally:
            queue.stop()

    def test_error_propagation_limits(self):
        """Test that errors are contained and don't propagate beyond boundaries."""

        async def async_test():
            # Test Matrix message handling error containment
            from mmrelay.matrix_utils import on_room_message

            mock_room = MagicMock()
            mock_room.room_id = "!room:matrix.org"

            mock_event = MagicMock()
            mock_event.sender = "@user:matrix.org"
            mock_event.body = "test message"

            # Mock plugin that raises exception
            mock_plugin = MagicMock()
            mock_plugin.handle_room_message = AsyncMock(
                side_effect=Exception("Plugin error")
            )

            with patch(
                "mmrelay.plugin_loader.load_plugins", return_value=[mock_plugin]
            ):
                with patch("mmrelay.matrix_utils.logger") as mock_logger:
                    # Set up config
                    import mmrelay.matrix_utils

                    mmrelay.matrix_utils.config = {
                        "matrix_rooms": [
                            {"id": "!room:matrix.org", "meshtastic_channel": 0}
                        ]
                    }
                    mmrelay.matrix_utils.matrix_rooms = [
                        {"id": "!room:matrix.org", "meshtastic_channel": 0}
                    ]

                    # Should not raise exception despite plugin failure
                    try:
                        await on_room_message(mock_room, mock_event)
                    except Exception as e:
                        self.fail(f"Error propagated beyond boundary: {e}")

                    # Should have logged the error
                    mock_logger.error.assert_called()

        asyncio.run(async_test())

    def test_resource_exhaustion_handling(self):
        """Test handling of resource exhaustion scenarios."""
        queue = MessageQueue()
        queue.start(message_delay=0.01)

        def memory_intensive_function():
            # Simulate memory-intensive operation
            try:
                # Try to allocate large amount of memory
                [0] * (10**6)  # 1 million integers
                return MagicMock(id="memory_id")
            except MemoryError as e:
                raise Exception("Out of memory") from e

        try:
            # Queue many memory-intensive operations
            enqueued_count = 0
            for i in range(100):
                success = queue.enqueue(
                    memory_intensive_function, description=f"Memory test {i}"
                )
                if success:
                    enqueued_count += 1
                else:
                    break  # Queue full

            # Should have enqueued some messages (up to queue limit)
            self.assertGreater(enqueued_count, 0)
            self.assertLessEqual(enqueued_count, 100)  # Queue limit

            # Wait for processing
            import time

            time.sleep(2)

            # Queue should still be running despite resource pressure
            self.assertTrue(queue.is_running())

        finally:
            queue.stop()

    def test_configuration_error_fallbacks(self):
        """Test fallback behavior when configuration is invalid or missing."""
        # Test with completely missing config
        with patch("mmrelay.meshtastic_utils.logger"):
            import mmrelay.meshtastic_utils

            mmrelay.meshtastic_utils.config = None
            mmrelay.meshtastic_utils.matrix_rooms = None

            packet = {
                "decoded": {"text": "test message", "portnum": 1},
                "fromId": "!12345678",
                "channel": 0,
            }

            mock_interface = MagicMock()

            # Should handle missing config gracefully
            try:
                on_meshtastic_message(packet, mock_interface)
            except Exception as e:
                self.fail(f"Failed to handle missing config: {e}")

        # Test with malformed config
        with patch("mmrelay.meshtastic_utils.logger"):
            mmrelay.meshtastic_utils.config = {"invalid": "config"}
            mmrelay.meshtastic_utils.matrix_rooms = []

            # Should handle malformed config gracefully
            try:
                on_meshtastic_message(packet, mock_interface)
            except Exception as e:
                self.fail(f"Failed to handle malformed config: {e}")


if __name__ == "__main__":
    unittest.main()
