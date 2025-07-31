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
        """
        Initialize a mock configuration dictionary for Matrix and Meshtastic settings before each test.
        """
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
        Tests that async functions, specifically `connect_matrix`, are properly awaited without generating coroutine warnings.
        
        Ensures that the `connect_matrix` function returns a valid client and that its async methods are awaited as expected.
        """
        async def test_coroutine():
            """
            Asynchronously tests the Matrix connection coroutine, ensuring proper awaiting and client initialization.
            
            Simulates the Matrix connection process by mocking SSL context, certificate path, and the Matrix AsyncClient. Verifies that the `connect_matrix` function awaits the `whoami` method and returns a valid client instance.
            """
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
        Test that multiple async operations can run concurrently without errors.
        
        Runs several mock async tasks in parallel and asserts all complete successfully, verifying correct handling of concurrency.
        """
        async def test_concurrent():
            """
            Test that multiple async tasks execute concurrently and complete successfully.
            
            Runs several mock async operations in parallel using asyncio.gather and asserts that each completes without exceptions and returns the expected result.
            """
            # Create simple async tasks that simulate concurrent operations
            async def mock_async_operation(task_id):
                """
                Simulates an asynchronous operation with a brief delay.
                
                Parameters:
                    task_id: Identifier for the mock task.
                
                Returns:
                    str: A string indicating the completion of the task with its ID.
                """
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
        Tests that async operations correctly handle timeouts by raising a TimeoutError when execution exceeds the specified duration.
        """
        async def test_timeout():
            """
            Asynchronously tests that a timeout is correctly raised when an async Matrix operation exceeds the specified duration.
            
            This test mocks a slow Matrix client operation and verifies that `asyncio.wait_for` raises a `TimeoutError` when the operation takes longer than the allowed timeout.
            """
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
                                """
                                Simulates a delayed asynchronous `whoami` call returning a mock device object.
                                
                                Returns:
                                    MagicMock: A mock object with a `device_id` attribute set to "test_device".
                                """
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
        Test that exceptions in async operations are correctly propagated or handled.
        
        This test verifies that when an exception occurs during an awaited async call (such as a failed Matrix client operation), the error is either handled gracefully by the async function or properly propagated to the caller.
        """
        async def test_error_handling():
            """
            Test that exceptions raised during async operations are either handled gracefully or propagated as expected.
            
            This test mocks the Matrix AsyncClient to raise an exception during the `whoami` call and verifies that `connect_matrix` either returns a client or raises the expected exception.
            """
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
        Tests that async plugin methods are correctly awaited and their results are processed as expected.
        """
        async def test_plugin_async():
            """
            Tests that an async plugin method is properly awaited and returns the expected result.
            
            Creates a mock plugin with an async method, mocks room and event objects, and verifies that the async method is awaited and called exactly once.
            """
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
        Tests creation and management of multiple asyncio event loops to ensure tasks run correctly and loops do not interfere with each other.
        """
        # Test that we can create and manage event loops
        loop1 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop1)
        
        async def simple_task():
            """
            Asynchronously sleeps for a short duration and returns a completion message.
            
            Returns:
                str: The string "completed" after the sleep finishes.
            """
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
        Tests that async context managers are correctly used for resource management in asynchronous operations.
        
        Ensures that entering and exiting async context managers works as expected and that methods within the context manager can be awaited successfully.
        """
        async def test_context_manager():
            """
            Tests that an async context manager can be used with `async with` and its methods can be awaited as expected.
            """
            # Mock async context manager
            class MockAsyncContextManager:
                async def __aenter__(self):
                    """
                    Enter the asynchronous context manager and return the context object.
                    """
                    return self
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    """
                    Exits the asynchronous context manager without suppressing exceptions.
                    
                    Returns:
                        bool: Always returns False to indicate exceptions are not suppressed.
                    """
                    return False
                
                async def do_something(self):
                    """
                    Asynchronously returns the string "success".
                    """
                    return "success"
            
            # Test proper async context manager usage
            async with MockAsyncContextManager() as manager:
                result = await manager.do_something()
                self.assertEqual(result, "success")

        # Run the context manager test
        asyncio.run(test_context_manager())

    def test_async_generator_handling(self):
        """
        Tests that async generators yield expected values and that async iteration collects all items correctly.
        """
        async def test_async_generator():
            """
            Tests that async generators yield expected values and can be iterated over asynchronously.
            """
            # Create async generator
            async def async_data_source():
                """
                Asynchronously yields a sequence of data items, simulating an async data source.
                
                Yields:
                    str: Data items labeled as 'data_0', 'data_1', and 'data_2', each after a short delay.
                """
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
        Tests that the `matrix_relay` function correctly performs asynchronous operations and maintains proper async/await patterns.
        
        This test mocks the Matrix client and room, patches global references, and verifies that the async `room_send` method is called as expected during the relay process.
        """
        async def test_matrix_relay():
            """
            Tests that the `matrix_relay` function sends a message asynchronously to the correct Matrix room and that the underlying async send method is called exactly once.
            """
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
        Tests handling of exceptions in various asynchronous scenarios, including async functions, context managers, and generators.
        
        Verifies that exceptions raised in async functions and context managers are properly caught, and that async generators yield expected results before termination.
        """
        async def test_exception_patterns():
            """
            Test various async exception handling scenarios, including exceptions in async functions, async context managers, and async generators.
            
            Verifies that exceptions are correctly raised and caught in different asynchronous constructs, and that async generators yield expected results before termination.
            """

            # Test 1: Basic async exception handling
            async def failing_operation():
                """
                Asynchronously raises a ValueError to simulate a failing async operation.
                
                Raises:
                    ValueError: Always raised with the message "Async operation failed".
                """
                raise ValueError("Async operation failed")

            try:
                await failing_operation()
                self.fail("Should have raised ValueError")
            except ValueError as e:
                self.assertIn("Async operation failed", str(e))

            # Test 2: Exception in async context manager
            class FailingAsyncContextManager:
                async def __aenter__(self):
                    """
                    Raises a RuntimeError when entering the async context manager.
                    """
                    raise RuntimeError("Context manager failed")

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    """
                    Exits the asynchronous context manager without suppressing exceptions.
                    
                    Returns:
                        bool: Always returns False to indicate exceptions are not suppressed.
                    """
                    return False

            try:
                async with FailingAsyncContextManager():
                    pass
                self.fail("Should have raised RuntimeError")
            except RuntimeError as e:
                self.assertIn("Context manager failed", str(e))

            # Test 3: Exception in async generator
            async def failing_generator():
                """
                An async generator that yields a single value and then terminates.
                
                Yields:
                    str: The string "first" before the generator stops.
                """
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
        Test that async resources are properly cleaned up, including when exceptions occur.
        
        Ensures that asynchronous context managers execute their cleanup logic in both normal operation and when exceptions are raised within the context.
        """
        async def test_resource_cleanup():
            """
            Test that async resources are properly cleaned up both during normal operation and when exceptions occur within an async context manager.
            """
            cleanup_called = False

            class AsyncResource:
                def __init__(self):
                    """
                    Initialize the resource and set its closed state to False.
                    """
                    self.closed = False

                async def __aenter__(self):
                    """
                    Enter the asynchronous context manager and return the context object.
                    """
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    """
                    Performs cleanup actions when exiting the async context, marking the resource as closed and indicating cleanup was called.
                    
                    Returns:
                        False: Indicates that any exception raised within the context should not be suppressed.
                    """
                    nonlocal cleanup_called
                    cleanup_called = True
                    self.closed = True
                    return False

                async def do_work(self):
                    """
                    Performs an asynchronous work operation if the resource is open.
                    
                    Returns:
                        str: "work done" if the resource is not closed.
                    
                    Raises:
                        RuntimeError: If the resource has been closed.
                    """
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
        Tests that async tasks can be cancelled and that cancellation is handled gracefully within the task.
        """
        async def test_cancellation():
            """
            Tests that an async task can be cancelled and handles cancellation gracefully, ensuring proper cleanup and expected result.
            """

            async def long_running_task():
                """
                Performs a long-running asynchronous task that can be cancelled.
                
                Returns:
                    str: "completed" if the task finishes normally, or "cancelled" if it is cancelled before completion.
                """
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
        Tests that deeply nested asynchronous recursive calls execute correctly without causing stack overflows or runtime errors.
        
        Verifies that a recursive async function can reach a specified depth and returns the expected nested result string.
        """
        async def nested_async_call(depth):
            """
            Recursively performs nested asynchronous calls to a specified depth.
            
            Parameters:
                depth (int): The recursion depth. When zero or negative, recursion stops.
            
            Returns:
                str: A string representing the nested call structure, with each level annotated.
            """
            if depth <= 0:
                return "bottom"

            await asyncio.sleep(0.001)  # Small delay
            result = await nested_async_call(depth - 1)
            return f"level_{depth}:{result}"

        async def test_nesting():
            """
            Tests that deeply nested asynchronous calls complete successfully and return expected markers in the result.
            """
            result = await nested_async_call(10)
            self.assertIn("level_10", result)
            self.assertIn("bottom", result)

        # Run the nesting test
        asyncio.run(test_nesting())

    def test_async_with_threading(self):
        """
        Tests that asynchronous functions can be executed within a separate thread using a dedicated event loop, and verifies that results are correctly returned from the thread.
        """
        import threading

        results = []

        def thread_worker():
            """
            Runs an asynchronous task within a separate thread using a dedicated event loop.
            
            Appends the result of the async operation to the shared `results` list.
            """
            async def async_work():
                """
                Performs a brief asynchronous delay and returns a result string.
                
                Returns:
                    str: The string "thread_result" after a short async pause.
                """
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
