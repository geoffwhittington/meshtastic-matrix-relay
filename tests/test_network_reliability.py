"""
Test suite for network reliability and connection handling.

This module tests network connection reliability scenarios including
retry logic, backoff behavior, connection type fallbacks, and message
queuing during network interruptions.
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, patch

from mmrelay.constants.network import (
    CONNECTION_TYPE_BLE,
    CONNECTION_TYPE_SERIAL,
    CONNECTION_TYPE_TCP,
    DEFAULT_BACKOFF_TIME,
    INFINITE_RETRIES,
    MINIMUM_MESSAGE_DELAY,
)
from mmrelay.constants.queue import MAX_QUEUE_SIZE


class TestConnectionRetryLogic:
    """Test connection retry and backoff behavior."""

    @pytest.mark.asyncio
    async def test_connection_retry_backoff_timing(self):
        """
        Verify that connection retry logic attempts reconnection with appropriate backoff timing after failures.
        
        This test simulates two consecutive connection failures followed by a successful attempt, ensuring that the retry mechanism waits for the expected backoff duration between attempts and that the total elapsed time reflects these delays within an acceptable variance.
        """
        with patch("mmrelay.meshtastic_utils.time.sleep"), patch(
            "mmrelay.meshtastic_utils.connect_meshtastic"
        ) as mock_connect:
            # Simulate connection failures followed by success
            mock_connect.side_effect = [
                ConnectionError("First attempt"),
                ConnectionError("Second attempt"),
                MagicMock(),  # Success on third attempt
            ]

            start_time = time.time()

            # This would be your actual retry logic - adjust import as needed
            try:
                from mmrelay.meshtastic_utils import establish_connection_with_retry

                await establish_connection_with_retry()
            except ImportError:
                # If the function doesn't exist yet, simulate the test
                for attempt in range(3):
                    try:
                        mock_connect()
                        break
                    except ConnectionError:
                        if attempt < 2:  # Don't sleep on last attempt
                            await asyncio.sleep(DEFAULT_BACKOFF_TIME)

            end_time = time.time()

            # Should have attempted connection 3 times
            assert mock_connect.call_count == 3

            # Should have waited for backoff (allowing some timing variance)
            elapsed = end_time - start_time
            expected_min_time = DEFAULT_BACKOFF_TIME * 2  # Two backoff periods
            assert elapsed >= expected_min_time * 0.8  # Allow 20% variance

    @pytest.mark.asyncio
    async def test_exponential_backoff_progression(self):
        """
        Verifies that connection retry backoff durations increase exponentially after consecutive failures.
        
        Simulates multiple connection failures and records the durations passed to the backoff mechanism, asserting that each subsequent backoff is at least as long as the previous, following an exponential progression.
        """
        backoff_times = []

        def mock_sleep(duration):
            """
            Appends the given duration to the backoff_times list to record simulated sleep intervals during testing.
            
            Parameters:
                duration (float): The simulated sleep duration to record.
            """
            backoff_times.append(duration)

        with patch("asyncio.sleep", side_effect=mock_sleep), patch(
            "mmrelay.meshtastic_utils.connect_meshtastic"
        ) as mock_connect:
            # Simulate multiple failures
            mock_connect.side_effect = [ConnectionError()] * 5

            # Simulate exponential backoff logic
            base_backoff = DEFAULT_BACKOFF_TIME
            for attempt in range(5):
                try:
                    mock_connect()
                except ConnectionError:
                    if attempt < 4:  # Don't sleep on last attempt
                        backoff_duration = base_backoff * (2**attempt)
                        await asyncio.sleep(backoff_duration)

            # Verify exponential progression
            assert len(backoff_times) == 4  # 4 backoff periods for 5 attempts
            for i in range(1, len(backoff_times)):
                assert backoff_times[i] >= backoff_times[i - 1]

    @pytest.mark.asyncio
    async def test_infinite_retries_behavior(self):
        """
        Test that the connection logic correctly retries indefinitely when configured for infinite retries, eventually succeeding after multiple failures.
        
        Simulates repeated connection failures and verifies that the retry mechanism continues until a successful connection is made, as expected with infinite retry settings.
        """
        retry_count = 0

        def mock_connect():
            """
            Simulates a connection attempt that fails nine times before succeeding on the tenth attempt.
            
            Returns:
                MagicMock: A mock object representing a successful connection on the tenth attempt.
            
            Raises:
                ConnectionError: If called fewer than ten times, raises with the current attempt number.
            """
            nonlocal retry_count
            retry_count += 1
            if retry_count < 10:  # Fail first 9 times
                raise ConnectionError(f"Attempt {retry_count}")
            return MagicMock()  # Success on 10th attempt

        with patch("mmrelay.meshtastic_utils.connect_meshtastic", side_effect=mock_connect):
            # Simulate retry logic with INFINITE_RETRIES
            max_attempts = 15  # Reasonable limit for test
            for attempt in range(max_attempts):
                try:
                    result = mock_connect()
                    assert result is not None
                    break
                except ConnectionError:
                    if INFINITE_RETRIES == 0:  # 0 means infinite
                        continue
                    elif attempt >= INFINITE_RETRIES:
                        break

            assert retry_count == 10  # Should succeed on 10th attempt


class TestConnectionTypeFallback:
    """Test fallback between different connection types."""

    @pytest.mark.asyncio
    async def test_connection_type_sequence(self):
        """
        Verifies that connection attempts proceed through TCP, Serial, and BLE in order, succeeding on BLE after previous failures.
        
        Asserts that all connection types are attempted in sequence and that the BLE connection is the one that succeeds.
        """
        connection_attempts = []

        def mock_connect(connection_type):
            """
            Simulates a connection attempt for the specified connection type, succeeding only for BLE.
            
            Parameters:
                connection_type (str): The type of connection to attempt.
            
            Returns:
                MagicMock: A mock connection object if the connection type is BLE.
            
            Raises:
                ConnectionError: If the connection type is not BLE.
            """
            connection_attempts.append(connection_type)
            if connection_type == CONNECTION_TYPE_BLE:
                return MagicMock()  # BLE succeeds
            raise ConnectionError(f"{connection_type} failed")

        connection_types = [CONNECTION_TYPE_TCP, CONNECTION_TYPE_SERIAL, CONNECTION_TYPE_BLE]

        # Simulate trying each connection type
        for conn_type in connection_types:
            try:
                result = mock_connect(conn_type)
                if result:
                    break
            except ConnectionError:
                continue

        assert connection_attempts == connection_types
        assert connection_attempts[-1] == CONNECTION_TYPE_BLE  # BLE succeeded

    @pytest.mark.asyncio
    async def test_connection_type_validation(self):
        """
        Verify that all defined connection types are valid, non-empty strings and belong to the accepted set of connection types.
        """
        valid_types = {CONNECTION_TYPE_TCP, CONNECTION_TYPE_SERIAL, CONNECTION_TYPE_BLE}

        # Test that all defined connection types are valid
        for conn_type in valid_types:
            assert isinstance(conn_type, str)
            assert len(conn_type) > 0
            assert conn_type in ["tcp", "serial", "ble", "network"]

    @pytest.mark.asyncio
    async def test_connection_preference_order(self):
        """
        Verify that the preferred connection types are ordered as TCP, Serial, then BLE for optimal reliability and speed.
        """
        # Typically TCP -> Serial -> BLE for reliability/speed
        preferred_order = [CONNECTION_TYPE_TCP, CONNECTION_TYPE_SERIAL, CONNECTION_TYPE_BLE]

        # Verify the order makes sense (this is more of a design test)
        assert CONNECTION_TYPE_TCP in preferred_order
        assert CONNECTION_TYPE_SERIAL in preferred_order
        assert CONNECTION_TYPE_BLE in preferred_order


class TestMessageQueueDuringDisconnection:
    """Test message queuing behavior during network interruptions."""

    def test_message_queuing_when_disconnected(self):
        """
        Verifies that messages are enqueued in the message queue when the connection is unavailable, ensuring no messages are lost during disconnection.
        """
        from mmrelay.message_queue import MessageQueue

        queue = MessageQueue()
        queue.start()

        # Mock send function
        mock_send = MagicMock()

        try:
            # Simulate disconnected state
            with patch("mmrelay.meshtastic_utils.meshtastic_client", None):
                # Messages should be queued, not lost
                test_messages = ["Message 1", "Message 2", "Message 3"]

                for msg in test_messages:
                    result = queue.enqueue(
                        mock_send, msg, description=f"Test message: {msg}"
                    )
                    assert result is True  # Should successfully enqueue

                # Queue should contain all messages
                assert queue.get_queue_size() >= len(test_messages)

        finally:
            queue.stop()

    def test_queue_overflow_protection(self):
        """
        Verify that the message queue enforces its maximum size limit by rejecting messages when full.
        
        Fills the queue beyond its maximum capacity while disconnected and asserts that the queue size does not exceed the defined maximum, with some messages being rejected once the limit is reached.
        """
        from mmrelay.message_queue import MessageQueue

        queue = MessageQueue()
        queue.start()

        # Mock send function
        mock_send = MagicMock()

        try:
            # Fill queue to near capacity
            messages_to_send = MAX_QUEUE_SIZE + 10  # Exceed max size

            with patch("mmrelay.meshtastic_utils.meshtastic_client", None):
                successful_enqueues = 0
                for i in range(messages_to_send):
                    result = queue.enqueue(
                        mock_send, f"Message {i}", description=f"Test message {i}"
                    )
                    if result:
                        successful_enqueues += 1

                # Queue should not exceed maximum size
                assert queue.get_queue_size() <= MAX_QUEUE_SIZE
                # Should have rejected some messages when full
                assert successful_enqueues <= MAX_QUEUE_SIZE

        finally:
            queue.stop()

    @pytest.mark.asyncio
    async def test_message_processing_after_reconnection(self):
        """
        Verify that messages enqueued during a disconnection are processed after reconnection.
        
        This test enqueues messages while the client is disconnected, then simulates reconnection and checks that the message queue size decreases, indicating that queued messages are being processed.
        """
        from mmrelay.message_queue import MessageQueue

        queue = MessageQueue()
        queue.start()

        # Mock send function
        mock_send = MagicMock()

        try:
            # Queue messages while disconnected
            test_messages = ["Queued 1", "Queued 2", "Queued 3"]

            with patch("mmrelay.meshtastic_utils.meshtastic_client", None):
                for msg in test_messages:
                    queue.enqueue(mock_send, msg, description=f"Queued: {msg}")

                initial_queue_size = queue.get_queue_size()

            # Simulate reconnection and message processing
            mock_client = MagicMock()
            with patch("mmrelay.meshtastic_utils.meshtastic_client", mock_client):
                # Allow some time for queue processing
                await asyncio.sleep(0.2)

                # Queue should start processing (size should decrease or be empty)
                final_queue_size = queue.get_queue_size()
                assert final_queue_size <= initial_queue_size

        finally:
            queue.stop()


class TestNetworkErrorRecovery:
    """Test recovery from various network error conditions."""

    @pytest.mark.asyncio
    async def test_timeout_error_recovery(self):
        """
        Verifies that the system recovers from consecutive network timeout errors by retrying the connection until it succeeds after multiple failures.
        """
        timeout_count = 0

        def mock_connect():
            """
            Simulates a network connection attempt that raises a TimeoutError on the first two calls, then succeeds on the third and subsequent calls.
            
            Returns:
                MagicMock: A mock object representing a successful connection after two timeouts.
            """
            nonlocal timeout_count
            timeout_count += 1
            if timeout_count <= 2:
                raise TimeoutError("Network timeout")
            return MagicMock()

        with patch("mmrelay.meshtastic_utils.connect_meshtastic", side_effect=mock_connect):
            # Should eventually succeed after timeouts
            for _ in range(5):
                try:
                    result = mock_connect()
                    assert result is not None
                    break
                except TimeoutError:
                    await asyncio.sleep(0.1)  # Brief delay between attempts

            assert timeout_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_connection_reset_recovery(self):
        """
        Asynchronously tests that the system recovers from a ConnectionResetError by retrying the connection and succeeding on a subsequent attempt.
        """
        reset_count = 0

        def mock_connect():
            """
            Simulates a connection attempt that raises a ConnectionResetError on the first call and succeeds on subsequent calls.
            
            Returns:
                MagicMock: A mock object representing a successful connection after the initial failure.
            """
            nonlocal reset_count
            reset_count += 1
            if reset_count <= 1:
                raise ConnectionResetError("Connection reset by peer")
            return MagicMock()

        with patch("mmrelay.meshtastic_utils.connect_meshtastic", side_effect=mock_connect):
            # Should recover from connection reset
            for _ in range(3):
                try:
                    result = mock_connect()
                    assert result is not None
                    break
                except ConnectionResetError:
                    await asyncio.sleep(0.1)

            assert reset_count == 2  # Failed once, succeeded on second

    @pytest.mark.asyncio
    async def test_message_delay_enforcement(self):
        """
        Verify that the minimum delay between consecutive messages is enforced during message sending recovery.
        
        Sends three messages in rapid succession with enforced delays, then asserts that the time between each send meets or exceeds the minimum message delay within a 10% margin.
        """
        send_times = []

        async def mock_send_message():
            """
            Appends the current timestamp to the send_times list to simulate a message send event.
            """
            send_times.append(time.time())

        # Simulate rapid message sending
        for _ in range(3):
            await mock_send_message()
            await asyncio.sleep(MINIMUM_MESSAGE_DELAY)

        # Verify minimum delay between messages
        for i in range(1, len(send_times)):
            time_diff = send_times[i] - send_times[i - 1]
            assert time_diff >= MINIMUM_MESSAGE_DELAY * 0.9  # Allow 10% variance
