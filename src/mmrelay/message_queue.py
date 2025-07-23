"""
Message queue system for MMRelay.

Provides transparent message queuing with rate limiting to prevent overwhelming
the Meshtastic network. Messages are queued in memory and sent at the configured
rate, respecting connection state and firmware constraints.
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from queue import Queue
from typing import Callable

from mmrelay.log_utils import get_logger

logger = get_logger(name="MessageQueue")


@dataclass
class QueuedMessage:
    """Represents a message in the queue with metadata."""

    timestamp: float
    send_function: Callable
    args: tuple
    kwargs: dict
    description: str = ""


class MessageQueue:
    """
    Simple FIFO message queue with rate limiting for Meshtastic messages.

    Queues messages in memory and sends them in order at the configured rate to prevent
    overwhelming the mesh network. Respects connection state and automatically
    pauses during reconnections.
    """

    def __init__(self):
        self._queue = Queue()
        self._processor_task = None
        self._running = False
        self._lock = threading.Lock()
        self._last_send_time = 0.0
        self._rate_limit = 2.2  # Default rate limit in seconds

    def start(self, rate_limit: float = 2.2):
        """
        Start the message queue processor.

        Args:
            rate_limit: Minimum seconds between messages (default: 2.2)
        """
        with self._lock:
            if self._running:
                return

            self._rate_limit = max(rate_limit, 2.0)  # Enforce firmware minimum
            self._running = True

            # Start the processor in the event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._processor_task = loop.create_task(self._process_queue())
                    logger.info(
                        f"Message queue started with {self._rate_limit}s rate limit"
                    )
                else:
                    # Event loop exists but not running yet, defer startup
                    logger.debug(
                        "Event loop not running yet, will start processor later"
                    )
            except RuntimeError:
                # No event loop running, will start when one is available
                logger.debug(
                    "No event loop available, queue processor will start later"
                )

    def stop(self):
        """Stop the message queue processor."""
        with self._lock:
            if not self._running:
                return

            self._running = False

            if self._processor_task:
                self._processor_task.cancel()
                self._processor_task = None

            logger.info("Message queue stopped")

    def enqueue(
        self, send_function: Callable, *args, description: str = "", **kwargs
    ) -> bool:
        """
        Enqueue a message for sending.

        Args:
            send_function: Function to call to send the message
            *args: Arguments to pass to send_function
            description: Human-readable description for logging
            **kwargs: Keyword arguments to pass to send_function

        Returns:
            bool: True if message was queued, False if queue is full
        """
        if not self._running:
            # Queue not started, send immediately as fallback
            logger.warning(f"Queue not running, sending message immediately: {description}")
            try:
                result = send_function(*args, **kwargs)
                logger.info(f"Immediate send {'successful' if result else 'failed'}: {description}")
                return result is not None
            except Exception as e:
                logger.error(f"Error sending message immediately: {e}")
                return False

        # Ensure processor is started if event loop is now available
        self.ensure_processor_started()

        # Check queue size to prevent memory issues
        if self._queue.qsize() >= 500:  # Increased limit for better throughput
            logger.warning(f"Message queue full ({self._queue.qsize()}/500), dropping message: {description}")
            return False

        message = QueuedMessage(
            timestamp=time.time(),
            send_function=send_function,
            args=args,
            kwargs=kwargs,
            description=description,
        )

        self._queue.put(message)
        logger.info(f"Queued message ({self._queue.qsize()}/500): {description}")
        return True

    def get_queue_size(self) -> int:
        """Get current number of messages in queue."""
        return self._queue.qsize()

    def is_running(self) -> bool:
        """Check if queue processor is running."""
        return self._running

    def get_status(self) -> dict:
        """Get detailed queue status for debugging."""
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "rate_limit": self._rate_limit,
            "processor_task_active": self._processor_task is not None and not self._processor_task.done() if self._processor_task else False,
            "last_send_time": self._last_send_time,
            "time_since_last_send": time.time() - self._last_send_time if self._last_send_time > 0 else None
        }

    def ensure_processor_started(self):
        """Ensure the processor task is started if the queue is running."""
        if self._running and self._processor_task is None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._processor_task = loop.create_task(self._process_queue())
                    logger.info(
                        f"Message queue processor started with {self._rate_limit}s rate limit"
                    )
            except RuntimeError:
                # Still no event loop available
                pass

    async def _process_queue(self):
        """Process messages from the queue with rate limiting."""
        logger.debug("Message queue processor started")

        while self._running:
            try:
                # Check if we need to wait for rate limiting
                time_since_last = time.time() - self._last_send_time
                if time_since_last < self._rate_limit:
                    wait_time = self._rate_limit - time_since_last
                    await asyncio.sleep(wait_time)

                # Get next message (non-blocking)
                try:
                    message = self._queue.get_nowait()
                except Exception:
                    # No messages, wait a bit and continue
                    await asyncio.sleep(0.1)
                    continue

                # Check if we should send (connection state, etc.)
                if not self._should_send_message():
                    # Put message back and wait
                    logger.debug(f"Connection not ready, requeueing message: {message.description}")
                    self._queue.put(message)
                    await asyncio.sleep(1.0)
                    continue

                # Send the message
                try:
                    logger.info(f"Sending queued message: {message.description}")
                    result = message.send_function(*message.args, **message.kwargs)

                    # Update last send time
                    self._last_send_time = time.time()

                    if result is None:
                        logger.warning(
                            f"Message send returned None: {message.description}"
                        )
                    else:
                        logger.info(f"Successfully sent queued message: {message.description}")

                except Exception as e:
                    logger.error(
                        f"Error sending queued message '{message.description}': {e}"
                    )

                # Mark task as done
                self._queue.task_done()

            except asyncio.CancelledError:
                logger.debug("Message queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message queue processor: {e}")
                await asyncio.sleep(1.0)  # Prevent tight error loop

    def _should_send_message(self) -> bool:
        """
        Check if we should send a message now.

        Returns:
            bool: True if it's safe to send, False if we should wait
        """
        # Import here to avoid circular imports
        try:
            from mmrelay.meshtastic_utils import meshtastic_client, reconnecting

            # Don't send during reconnection
            if reconnecting:
                logger.debug("Not sending - reconnecting is True")
                return False

            # Don't send if no client
            if meshtastic_client is None:
                logger.debug("Not sending - meshtastic_client is None")
                return False

            # Check if client is connected
            if (
                hasattr(meshtastic_client, "isConnected")
                and not meshtastic_client.isConnected.is_set()
            ):
                logger.debug("Not sending - client not connected")
                return False

            logger.debug("Connection check passed - ready to send")
            return True

        except ImportError:
            # If we can't check connection state, assume it's okay
            logger.debug("Cannot check connection state - assuming OK")
            return True


# Global message queue instance
_message_queue = MessageQueue()


def get_message_queue() -> MessageQueue:
    """Get the global message queue instance."""
    return _message_queue


def start_message_queue(rate_limit: float = 2.2):
    """Start the global message queue with the specified rate limit."""
    _message_queue.start(rate_limit)


def stop_message_queue():
    """Stop the global message queue."""
    _message_queue.stop()


def queue_message(
    send_function: Callable, *args, description: str = "", **kwargs
) -> bool:
    """
    Queue a message for sending through the global message queue.

    Args:
        send_function: Function to call to send the message
        *args: Arguments to pass to send_function
        description: Human-readable description for logging
        **kwargs: Keyword arguments to pass to send_function

    Returns:
        bool: True if message was queued, False if failed
    """
    return _message_queue.enqueue(
        send_function, *args, description=description, **kwargs
    )


def get_queue_status() -> dict:
    """Get detailed status of the global message queue for debugging."""
    return _message_queue.get_status()
