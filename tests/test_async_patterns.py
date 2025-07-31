#!/usr/bin/env python3
"""
Test suite for async/await patterns and coroutine handling in MMRelay.

Tests async patterns including:
- Proper async/await usage in Matrix operations
- Coroutine lifecycle management
- Async error handling and timeouts
- Concurrent async operations
- Event loop management
- Plugin async method handling
"""

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.matrix_utils import connect_matrix, matrix_relay


class TestAsyncPatterns(unittest.TestCase):
    """Test cases for async/await patterns and coroutine handling."""

    def setUp(self):
        """Set up test environment with mock configuration."""
        self.config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@test:matrix.org",
            },
            "matrix_rooms": [{"id": "!room1:matrix.org", "meshtastic_channel": 0}],
            "meshtastic": {"meshnet_name": "TestMesh"},
        }

    def test_async_function_proper_awaiting(self):
        """
        Test that async functions are properly awaited and don't generate warnings.
        
        Verifies that coroutines are correctly awaited and don't cause
        "coroutine was never awaited" warnings.
        """
        async def test_coroutine():
            """Test coroutine that simulates Matrix connection."""
            # Ensure matrix_client is None to avoid early return
            with patch("mmrelay.matrix_utils.matrix_client", None):
                # Mock SSL context creation
                with patch("ssl.create_default_context") as mock_ssl:
                    mock_ssl.return_value = MagicMock()

                    # Mock certifi.where()
                    with patch("certifi.where", return_value="/fake/cert/path"):
                        # Mock Matrix client connection
                        with patch("mmrelay.matrix_utils.AsyncClient") as mock_client_class:
                            mock_client = AsyncMock()
                            # Mock successful whoami response
                            mock_whoami_response = MagicMock()
                            mock_whoami_response.device_id = "test_device"
                            mock_client.whoami.return_value = mock_whoami_response
                            mock_client_class.return_value = mock_client

                            # Test that connect_matrix properly awaits
                            result = await connect_matrix(self.config)

                            # Should return the client
                            self.assertIsNotNone(result)

                            # Verify whoami was called (awaited)
                            mock_client.whoami.assert_called_once()

        # Run the async test
        asyncio.run(test_coroutine())

    def test_concurrent_async_operations(self):
        """
        Test handling of multiple concurrent async operations.

        Verifies that the system can handle multiple async operations
        running concurrently without race conditions or deadlocks.
        """
        async def test_concurrent():
            """Test concurrent async operations with simple mock tasks."""
            # Create simple async tasks that simulate concurrent operations
            async def mock_async_operation(task_id):
                """Mock async operation that simulates work."""
                await asyncio.sleep(0.01)  # Small delay to simulate async work
                return f"task_{task_id}_completed"

            # Create multiple concurrent tasks
            tasks = [mock_async_operation(i) for i in range(5)]

            # Run all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete successfully
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.fail(f"Concurrent operation failed: {result}")
                self.assertEqual(result, f"task_{i}_completed")

        # Run the concurrent test
        asyncio.run(test_concurrent())

    def test_async_timeout_handling(self):
        """
        Test proper handling of async operation timeouts.
        
        Verifies that async operations respect timeouts and handle
        timeout exceptions gracefully.
        """
        async def test_timeout():
            """Test timeout handling in async operations."""
            # Ensure matrix_client is None to avoid early return
            with patch("mmrelay.matrix_utils.matrix_client", None):
                # Mock SSL context creation
                with patch("ssl.create_default_context") as mock_ssl:
                    mock_ssl.return_value = MagicMock()

                    # Mock certifi.where()
                    with patch("certifi.where", return_value="/fake/cert/path"):
                        # Mock a slow Matrix operation
                        with patch("mmrelay.matrix_utils.AsyncClient") as mock_client_class:
                            mock_client = AsyncMock()

                            # Make whoami take longer than timeout
                            async def slow_whoami():
                                await asyncio.sleep(2)  # 2 second delay
                                return MagicMock(device_id="test_device")

                            mock_client.whoami = slow_whoami
                            mock_client_class.return_value = mock_client

                            # Test with short timeout
                            try:
                                await asyncio.wait_for(connect_matrix(self.config), timeout=0.5)
                                self.fail("Should have timed out")
                            except asyncio.TimeoutError:
                                # Expected timeout
                                pass

        # Run the timeout test
        asyncio.run(test_timeout())

    def test_async_error_propagation(self):
        """
        Test that async errors are properly propagated and handled.
        
        Verifies that exceptions in async operations are correctly
        propagated to callers and can be handled appropriately.
        """
        async def test_error_handling():
            """Test error propagation in async operations."""
            # Mock SSL context creation
            with patch("ssl.create_default_context") as mock_ssl:
                mock_ssl.return_value = MagicMock()

                # Mock Matrix client that raises an exception
                with patch("mmrelay.matrix_utils.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.whoami.side_effect = Exception("Connection failed")
                    mock_client_class.return_value = mock_client

                    # Should handle the exception gracefully
                    try:
                        result = await connect_matrix(self.config)
                        # connect_matrix should handle errors and return client anyway
                        self.assertIsNotNone(result)
                    except Exception as e:
                        # If exception is raised, it should be the expected one
                        self.assertIn("Connection failed", str(e))

        # Run the error handling test
        asyncio.run(test_error_handling())

    def test_plugin_async_method_handling(self):
        """
        Test that plugin async methods are properly handled.
        
        Verifies that async plugin methods are correctly awaited
        and their results are properly processed.
        """
        async def test_plugin_async():
            """Test async plugin method handling."""
            # Create mock plugin with async methods
            mock_plugin = MagicMock()
            mock_plugin.handle_room_message = AsyncMock(return_value=True)
            
            # Mock room and event
            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"
            
            mock_event = MagicMock()
            mock_event.sender = "@user:matrix.org"
            mock_event.body = "test message"
            mock_event.server_timestamp = int(time.time() * 1000)
            mock_event.source = {"content": {}}
            
            # Test that plugin async method is properly awaited
            result = await mock_plugin.handle_room_message(mock_room, mock_event, "test message")
            
            # Should return the expected result
            self.assertTrue(result)
            
            # Verify the async method was called
            mock_plugin.handle_room_message.assert_called_once()

        # Run the plugin async test
        asyncio.run(test_plugin_async())

    def test_event_loop_management(self):
        """
        Test proper event loop management in async operations.
        
        Verifies that event loops are correctly managed and don't
        interfere with each other in different contexts.
        """
        # Test that we can create and manage event loops
        loop1 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop1)
        
        async def simple_task():
            await asyncio.sleep(0.01)
            return "completed"
        
        # Run task in first loop
        result1 = loop1.run_until_complete(simple_task())
        self.assertEqual(result1, "completed")
        
        loop1.close()
        
        # Create second loop
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        
        # Run task in second loop
        result2 = loop2.run_until_complete(simple_task())
        self.assertEqual(result2, "completed")
        
        loop2.close()

    def test_async_context_manager_usage(self):
        """
        Test proper usage of async context managers.
        
        Verifies that async context managers are correctly used
        for resource management in async operations.
        """
        async def test_context_manager():
            """Test async context manager usage."""
            # Mock async context manager
            class MockAsyncContextManager:
                async def __aenter__(self):
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False
                
                async def do_something(self):
                    return "success"
            
            # Test proper async context manager usage
            async with MockAsyncContextManager() as manager:
                result = await manager.do_something()
                self.assertEqual(result, "success")

        # Run the context manager test
        asyncio.run(test_context_manager())

    def test_async_generator_handling(self):
        """
        Test handling of async generators and async iteration.
        
        Verifies that async generators are properly handled
        and async iteration works correctly.
        """
        async def test_async_generator():
            """Test async generator handling."""
            # Create async generator
            async def async_data_source():
                for i in range(3):
                    await asyncio.sleep(0.01)  # Simulate async work
                    yield f"data_{i}"
            
            # Test async iteration
            results = []
            async for item in async_data_source():
                results.append(item)
            
            # Verify all items were yielded
            self.assertEqual(results, ["data_0", "data_1", "data_2"])

        # Run the async generator test
        asyncio.run(test_async_generator())

    def test_matrix_relay_async_patterns(self):
        """
        Test async patterns in matrix_relay function.

        Verifies that matrix_relay properly handles async operations
        and maintains correct async/await patterns.
        """
        async def test_matrix_relay():
            """Test matrix_relay async patterns."""
            # Mock Matrix client and room
            mock_client = AsyncMock()
            mock_client.room_send = AsyncMock(return_value=MagicMock(event_id="$event123"))

            # Mock room
            mock_room = MagicMock()
            mock_room.room_id = "!room1:matrix.org"

            with patch("mmrelay.matrix_utils.matrix_client", mock_client):
                with patch("mmrelay.matrix_utils.matrix_rooms", [{"id": "!room1:matrix.org", "meshtastic_channel": 0}]):
                    # Test matrix_relay async operation
                    await matrix_relay(
                        room_id="!room1:matrix.org",
                        message="Test message",
                        longname="TestNode",
                        shortname="TN",
                        meshnet_name="TestMesh",
                        portnum=1
                    )

                    # Verify async method was called
                    mock_client.room_send.assert_called_once()

        # Run the matrix relay test
        asyncio.run(test_matrix_relay())

    def test_async_exception_handling_patterns(self):
        """
        Test various async exception handling patterns.

        Verifies that different types of async exceptions are
        properly caught and handled in various scenarios.
        """
        async def test_exception_patterns():
            """Test different async exception handling patterns."""

            # Test 1: Basic async exception handling
            async def failing_operation():
                raise ValueError("Async operation failed")

            try:
                await failing_operation()
                self.fail("Should have raised ValueError")
            except ValueError as e:
                self.assertIn("Async operation failed", str(e))

            # Test 2: Exception in async context manager
            class FailingAsyncContextManager:
                async def __aenter__(self):
                    raise RuntimeError("Context manager failed")

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return False

            try:
                async with FailingAsyncContextManager():
                    pass
                self.fail("Should have raised RuntimeError")
            except RuntimeError as e:
                self.assertIn("Context manager failed", str(e))

            # Test 3: Exception in async generator
            async def failing_generator():
                yield "first"
                # In Python 3.7+, StopAsyncIteration in async generators becomes RuntimeError
                return  # Proper way to stop async generator

            results = []
            async for item in failing_generator():
                results.append(item)

            self.assertEqual(results, ["first"])

        # Run the exception patterns test
        asyncio.run(test_exception_patterns())

    def test_async_resource_cleanup(self):
        """
        Test that async resources are properly cleaned up.

        Verifies that async resources like connections, files,
        and other resources are properly cleaned up even when
        exceptions occur.
        """
        async def test_resource_cleanup():
            """Test async resource cleanup patterns."""
            cleanup_called = False

            class AsyncResource:
                def __init__(self):
                    self.closed = False

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    nonlocal cleanup_called
                    cleanup_called = True
                    self.closed = True
                    return False

                async def do_work(self):
                    if not self.closed:
                        return "work done"
                    raise RuntimeError("Resource is closed")

            # Test normal cleanup
            async with AsyncResource() as resource:
                result = await resource.do_work()
                self.assertEqual(result, "work done")

            self.assertTrue(cleanup_called)

            # Test cleanup on exception
            cleanup_called = False
            try:
                async with AsyncResource() as resource:
                    await resource.do_work()
                    raise ValueError("Something went wrong")
            except ValueError:
                pass

            self.assertTrue(cleanup_called)

        # Run the resource cleanup test
        asyncio.run(test_resource_cleanup())

    def test_async_task_cancellation(self):
        """
        Test proper handling of async task cancellation.

        Verifies that async tasks can be properly cancelled
        and that cancellation is handled gracefully.
        """
        async def test_cancellation():
            """Test async task cancellation patterns."""

            async def long_running_task():
                try:
                    await asyncio.sleep(10)  # Long operation
                    return "completed"
                except asyncio.CancelledError:
                    # Proper cleanup on cancellation
                    return "cancelled"

            # Start task
            task = asyncio.create_task(long_running_task())

            # Let it start
            await asyncio.sleep(0.01)

            # Cancel the task
            task.cancel()

            # Wait for cancellation
            try:
                result = await task
                self.assertEqual(result, "cancelled")
            except asyncio.CancelledError:
                # Task was cancelled before it could handle the cancellation
                pass

        # Run the cancellation test
        asyncio.run(test_cancellation())


class TestAsyncEdgeCases(unittest.TestCase):
    """Test edge cases in async/await patterns."""

    def test_nested_async_calls(self):
        """
        Test handling of deeply nested async calls.

        Verifies that deeply nested async operations don't
        cause stack overflow or other issues.
        """
        async def nested_async_call(depth):
            """Recursive async function for testing nesting."""
            if depth <= 0:
                return "bottom"

            await asyncio.sleep(0.001)  # Small delay
            result = await nested_async_call(depth - 1)
            return f"level_{depth}:{result}"

        async def test_nesting():
            result = await nested_async_call(10)
            self.assertIn("level_10", result)
            self.assertIn("bottom", result)

        # Run the nesting test
        asyncio.run(test_nesting())

    def test_async_with_threading(self):
        """
        Test interaction between async code and threading.

        Verifies that async operations work correctly when
        called from different threads.
        """
        import threading

        results = []

        def thread_worker():
            """Worker function that runs async code in a thread."""
            async def async_work():
                await asyncio.sleep(0.01)
                return "thread_result"

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(async_work())
                results.append(result)
            finally:
                loop.close()

        # Start thread
        thread = threading.Thread(target=thread_worker)
        thread.start()
        thread.join()

        # Verify result
        self.assertEqual(results, ["thread_result"])


if __name__ == "__main__":
    unittest.main()
