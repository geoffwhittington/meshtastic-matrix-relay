#!/usr/bin/env python3
"""
Test suite for Message Queue edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- Queue overflow scenarios
- Connection state edge cases
- Import errors and module loading failures
- Message mapping failures
- Processor task lifecycle edge cases
- Rate limiting boundary conditions
"""

import asyncio
import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.message_queue import MessageQueue, get_message_queue, queue_message


class TestMessageQueueEdgeCases(unittest.TestCase):
    """Test cases for Message Queue edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.queue = MessageQueue()

    def tearDown(self):
        """Clean up after each test method."""
        if self.queue.is_running():
            self.queue.stop()

    def test_queue_overflow_handling(self):
        """Test queue behavior when it reaches maximum capacity."""
        self.queue.start(message_delay=0.1)
        
        # Fill the queue to capacity
        for i in range(100):  # MAX_QUEUE_SIZE = 100
            success = self.queue.enqueue(
                lambda: None, 
                description=f"Message {i}"
            )
            self.assertTrue(success)
        
        # Next message should be rejected
        success = self.queue.enqueue(
            lambda: None, 
            description="Overflow message"
        )
        self.assertFalse(success)
        
        # Queue size should be at maximum
        self.assertEqual(self.queue.get_queue_size(), 100)

    def test_enqueue_when_not_running(self):
        """Test enqueue behavior when queue is not running."""
        # Queue is not started
        success = self.queue.enqueue(
            lambda: None, 
            description="Test message"
        )
        self.assertFalse(success)

    def test_start_with_invalid_message_delay(self):
        """Test start behavior with invalid message delay values."""
        # Test with delay below firmware minimum
        self.queue.start(message_delay=1.0)
        status = self.queue.get_status()
        self.assertEqual(status["message_delay"], 2.0)  # Should be corrected to minimum
        
        # Test with negative delay
        self.queue.stop()
        self.queue = MessageQueue()
        self.queue.start(message_delay=-1.0)
        status = self.queue.get_status()
        self.assertEqual(status["message_delay"], 2.0)  # Should be corrected to minimum

    def test_double_start(self):
        """Test that starting an already running queue is handled gracefully."""
        self.queue.start(message_delay=2.5)
        self.assertTrue(self.queue.is_running())
        
        # Starting again should not cause issues
        self.queue.start(message_delay=3.0)
        self.assertTrue(self.queue.is_running())
        
        # Message delay should not change
        status = self.queue.get_status()
        self.assertEqual(status["message_delay"], 2.5)

    def test_stop_when_not_running(self):
        """Test stop behavior when queue is not running."""
        # Should not raise an exception
        self.queue.stop()
        self.assertFalse(self.queue.is_running())

    @patch('mmrelay.message_queue.logger')
    def test_processor_import_error_handling(self, mock_logger):
        """Test processor behavior when import errors occur."""
        async def async_test():
            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()
            
            # Mock the import to raise ImportError
            with patch('mmrelay.message_queue.MessageQueue._should_send_message') as mock_should_send:
                mock_should_send.side_effect = ImportError("Module not found")
                
                # Queue a message
                success = self.queue.enqueue(lambda: "result", description="Test message")
                self.assertTrue(success)
                
                # Wait for processing
                await asyncio.sleep(0.2)
                
                # Queue should be stopped due to import error
                self.assertFalse(self.queue.is_running())

        asyncio.run(async_test())

    def test_message_mapping_with_invalid_result(self):
        """Test message mapping when result object doesn't have expected attributes."""
        async def async_test():
            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()
            
            # Mock send function that returns object without 'id' attribute
            def mock_send():
                result = MagicMock()
                del result.id  # Remove id attribute
                return result
            
            mapping_info = {
                "matrix_event_id": "test_event",
                "room_id": "test_room",
                "text": "test message"
            }
            
            success = self.queue.enqueue(
                mock_send, 
                description="Test message",
                mapping_info=mapping_info
            )
            self.assertTrue(success)
            
            # Wait for processing
            await asyncio.sleep(0.2)

        asyncio.run(async_test())

    def test_processor_task_cancellation(self):
        """Test processor task behavior when cancelled."""
        async def async_test():
            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()
            
            # Get the processor task
            processor_task = self.queue._processor_task
            self.assertIsNotNone(processor_task)
            
            # Cancel the task
            processor_task.cancel()
            
            # Wait for cancellation to complete
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
            
            # Task should be done
            self.assertTrue(processor_task.done())

        asyncio.run(async_test())

    def test_ensure_processor_started_without_event_loop(self):
        """Test ensure_processor_started when no event loop is available."""
        self.queue._running = True
        self.queue._processor_task = None
        
        # This should not raise an exception even without an event loop
        self.queue.ensure_processor_started()

    def test_rate_limiting_edge_cases(self):
        """Test rate limiting with edge case timing scenarios."""
        async def async_test():
            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()
            
            # Mock time to control timing
            with patch('time.time') as mock_time:
                mock_time.return_value = 1000.0
                
                # Queue first message
                success = self.queue.enqueue(lambda: "result1", description="Message 1")
                self.assertTrue(success)
                
                # Wait for first message to be processed
                await asyncio.sleep(0.2)
                
                # Advance time slightly (less than message delay)
                mock_time.return_value = 1000.05
                
                # Queue second message
                success = self.queue.enqueue(lambda: "result2", description="Message 2")
                self.assertTrue(success)
                
                # Should wait for rate limiting
                await asyncio.sleep(0.2)

        asyncio.run(async_test())

    def test_queue_status_with_no_sends(self):
        """Test queue status when no messages have been sent."""
        status = self.queue.get_status()
        
        self.assertFalse(status["running"])
        self.assertEqual(status["queue_size"], 0)
        self.assertEqual(status["last_send_time"], 0.0)
        self.assertIsNone(status["time_since_last_send"])

    def test_concurrent_enqueue_operations(self):
        """Test concurrent enqueue operations from multiple threads."""
        self.queue.start(message_delay=0.1)
        
        results = []
        
        def enqueue_messages(thread_id):
            for i in range(10):
                success = self.queue.enqueue(
                    lambda: f"result_{thread_id}_{i}",
                    description=f"Thread {thread_id} Message {i}"
                )
                results.append(success)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=enqueue_messages, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All enqueue operations should succeed (assuming queue capacity)
        successful_enqueues = sum(results)
        self.assertGreater(successful_enqueues, 0)

    def test_message_with_none_mapping_info(self):
        """Test message handling with None mapping info."""
        async def async_test():
            self.queue.start(message_delay=0.1)
            self.queue.ensure_processor_started()
            
            success = self.queue.enqueue(
                lambda: "result",
                description="Test message",
                mapping_info=None
            )
            self.assertTrue(success)
            
            # Wait for processing
            await asyncio.sleep(0.2)

        asyncio.run(async_test())

    def test_global_queue_functions(self):
        """Test global queue functions."""
        # Test get_message_queue
        global_queue = get_message_queue()
        self.assertIsNotNone(global_queue)
        
        # Test queue_message function
        success = queue_message(lambda: "result", description="Global test")
        # Should fail because global queue is not started
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
