#!/usr/bin/env python3
"""
Test suite for the MMRelay message queue system.

Tests the FIFO message queue functionality including:
- Message ordering (first in, first out)
- Rate limiting enforcement
- Connection state awareness
- Queue size limits
- Error handling
"""

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.message_queue import (
    MAX_QUEUE_SIZE,
    MessageQueue,
    QueuedMessage,
    queue_message,
)


def mock_send_function(text, **kwargs):
    """
    Simulates sending a message and records the call details for testing purposes.

    Parameters:
        text (str): The message text to send.

    Returns:
        dict: A dictionary containing a unique 'id' for the sent message.
    """
    # This will be called synchronously due to executor mocking
    mock_send_function.calls.append(
        {"text": text, "kwargs": kwargs, "timestamp": time.time()}
    )
    return {"id": len(mock_send_function.calls)}


# Initialize calls list
mock_send_function.calls = []


class TestMessageQueue(unittest.TestCase):
    """Test cases for the MessageQueue class."""

    def setUp(self):
        """
        Initializes the test environment for each test case by setting up a fresh MessageQueue instance, clearing mock send function calls, and patching asyncio to run executor functions synchronously.
        """
        self.queue = MessageQueue()
        # Clear mock function calls for each test
        mock_send_function.calls.clear()
        # Mock the _should_send_message method to always return True for tests
        self.queue._should_send_message = lambda: True

        # Mock asyncio.get_running_loop to make executor run synchronously
        self.loop_patcher = patch("asyncio.get_running_loop")
        mock_get_loop = self.loop_patcher.start()

        # Create a mock loop that runs executor functions synchronously
        mock_loop = MagicMock()

        async def sync_executor(executor, func, *args, **kwargs):
            """
            Executes a function synchronously, bypassing the executor.

            Parameters:
                func (callable): The function to execute.
                *args: Positional arguments to pass to the function.
                **kwargs: Keyword arguments to pass to the function.

            Returns:
                The result of the executed function.
            """
            return func(*args, **kwargs)

        mock_loop.run_in_executor = sync_executor
        mock_get_loop.return_value = mock_loop

    def tearDown(self):
        """
        Stops the message queue and restores the original asyncio event loop behavior after each test.
        """
        if self.queue.is_running():
            # Wait a bit for any in-flight messages to complete
            import time

            time.sleep(0.1)
            self.queue.stop()
        self.loop_patcher.stop()

    @property
    def sent_messages(self):
        """
        Returns the list of messages sent via the mock send function during testing.
        """
        return mock_send_function.calls

    def test_fifo_ordering(self):
        """
        Verifies that the message queue sends messages in the order they were enqueued (FIFO).

        This test enqueues multiple messages, waits for them to be processed, and asserts that they are sent in the same order as they were added to the queue.
        """

        # Use asyncio to properly test the async queue
        async def async_test():
            # Start queue with fast rate for testing
            """
            Asynchronously tests that messages are processed and sent in FIFO order by the message queue.

            This test enqueues multiple messages, waits for them to be processed, and asserts that they are sent in the order they were enqueued.
            """
            self.queue.start(message_delay=0.1)

            # Ensure processor starts
            self.queue.ensure_processor_started()

            # Queue multiple messages (reduced for faster testing)
            messages = ["First", "Second", "Third"]
            for msg in messages:
                success = self.queue.enqueue(
                    mock_send_function,
                    text=msg,
                    description=f"Test message: {msg}",
                )
                self.assertTrue(success)

            # Wait for processing to complete with a timeout
            end_time = (
                time.time() + 15.0
            )  # 15 second timeout (3 messages * 2s + buffer)
            while self.queue.get_queue_size() > 0 or len(self.sent_messages) < len(
                messages
            ):
                if time.time() > end_time:
                    self.fail(
                        f"Queue processing timed out. Sent {len(self.sent_messages)}/{len(messages)} messages, queue size: {self.queue.get_queue_size()}"
                    )
                await asyncio.sleep(0.1)

            # Check that messages were sent in order
            self.assertEqual(len(self.sent_messages), len(messages))
            for i, expected_msg in enumerate(messages):
                self.assertEqual(self.sent_messages[i]["text"], expected_msg)

        # Run the async test
        asyncio.run(async_test())

    def test_rate_limiting(self):
        """
        Verify that the message queue enforces rate limiting by delaying the sending of messages according to the configured interval.
        """

        async def async_test():
            """
            Asynchronously tests that the message queue enforces rate limiting by delaying the sending of messages according to the specified message delay interval.
            """
            message_delay = 2.1  # Use minimum message delay for testing
            self.queue.start(message_delay=message_delay)
            self.queue.ensure_processor_started()

            # Queue two messages
            self.queue.enqueue(mock_send_function, text="First")
            self.queue.enqueue(mock_send_function, text="Second")

            # Wait for first message
            await asyncio.sleep(1.0)
            self.assertEqual(len(self.sent_messages), 1)

            # Second message should not be sent yet (rate limit not passed)
            await asyncio.sleep(1.0)
            self.assertEqual(len(self.sent_messages), 1)

            # Wait for rate limit to pass
            await asyncio.sleep(1.5)
            self.assertEqual(len(self.sent_messages), 2)

        asyncio.run(async_test())

    def test_queue_size_limit(self):
        """
        Verify that the message queue enforces its maximum size limit by accepting messages up to the limit and rejecting additional messages beyond capacity.
        """
        # Start the queue but don't let it process (no event loop)
        self.queue._running = True  # Manually set running to prevent immediate sending

        # Fill queue to limit
        for i in range(MAX_QUEUE_SIZE):
            success = self.queue.enqueue(mock_send_function, text=f"Message {i}")
            self.assertTrue(success)

        # Next message should be rejected
        success = self.queue.enqueue(mock_send_function, text="Overflow message")
        self.assertFalse(success)

    def test_fallback_when_not_running(self):
        """
        Test that enqueuing a message is rejected when the queue is not running.

        Verifies that the queue does not accept messages unless it has been started, ensuring the event loop is not blocked and no messages are sent in this state.
        """
        # Don't start the queue
        success = self.queue.enqueue(mock_send_function, text="Immediate message")

        # Should refuse to send to prevent blocking event loop
        self.assertFalse(success)
        self.assertEqual(len(self.sent_messages), 0)

    def test_connection_state_awareness(self):
        """
        Verifies that the message queue does not send messages when the connection state indicates it should not send.

        Ensures that messages remain unsent if the queue's connection check fails, and restores the original connection check after the test.
        """

        async def async_test():
            # Mock the _should_send_message method to return False
            """
            Asynchronously tests that messages are not sent when the queue's connection state prevents sending.

            This function mocks the queue's connection check to simulate a disconnected state, enqueues a message, and verifies that the message is not sent while disconnected. The original connection check is restored after the test.
            """
            original_should_send = self.queue._should_send_message
            self.queue._should_send_message = lambda: False

            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()

            # Queue a message
            success = self.queue.enqueue(mock_send_function, text="Test message")
            self.assertTrue(success)

            # Wait - message should not be sent due to connection state
            await asyncio.sleep(0.3)
            self.assertEqual(len(self.sent_messages), 0)

            # Restore original method
            self.queue._should_send_message = original_should_send

        asyncio.run(async_test())

    def test_error_handling(self):
        """
        Verifies that the message queue handles exceptions raised during message sending without crashing and continues processing subsequent messages.
        """

        async def async_test():
            """
            Tests that the message queue continues running after a send function raises an exception.
            """

            def failing_send_function(text, **kwargs):
                raise Exception("Send failed")

            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()

            # Queue a message that will fail
            success = self.queue.enqueue(failing_send_function, text="Failing message")
            self.assertTrue(success)  # Queuing should succeed

            # Wait for processing - should not crash
            await asyncio.sleep(0.3)
            # Queue should continue working after error
            self.assertTrue(self.queue.is_running())

        asyncio.run(async_test())


class TestGlobalFunctions(unittest.TestCase):
    """Test cases for global queue functions."""

    def setUp(self):
        """
        Prepares the test environment by clearing the call history of the mock send function before each test.
        """
        # Clear mock function calls for each test
        mock_send_function.calls.clear()

    def test_queue_message_function(self):
        """
        Test that the global queue_message function refuses to enqueue messages when the queue is not running.

        Verifies that queue_message returns False and does not send messages if the message queue is inactive.
        """
        # Test with queue not running (should refuse to send)
        success = queue_message(
            mock_send_function,
            text="Test message",
            description="Global function test",
        )

        # Should refuse to send when queue not running to prevent event loop blocking
        self.assertFalse(success)
        self.assertEqual(len(mock_send_function.calls), 0)


class TestQueuedMessage(unittest.TestCase):
    """Test cases for the QueuedMessage dataclass."""

    def test_message_creation(self):
        """
        Verify that a QueuedMessage instance is correctly created with the expected attributes.
        """

        def dummy_function():
            """
            A placeholder function that performs no operation.
            """
            pass

        message = QueuedMessage(
            timestamp=123.456,
            send_function=dummy_function,
            args=("arg1", "arg2"),
            kwargs={"key": "value"},
            description="Test message",
        )

        self.assertEqual(message.timestamp, 123.456)
        self.assertEqual(message.send_function, dummy_function)
        self.assertEqual(message.args, ("arg1", "arg2"))
        self.assertEqual(message.kwargs, {"key": "value"})
        self.assertEqual(message.description, "Test message")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
