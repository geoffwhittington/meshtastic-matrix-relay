"""
Pytest configuration and fixtures for MMRelay tests.

This file sets up comprehensive mocking for external dependencies
to ensure tests can run without requiring actual hardware or network connections.
"""

import asyncio
import logging

# Preserve references to built-in modules that should NOT be mocked
import queue
import sys
import threading
import time
from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

import mmrelay.meshtastic_utils as mu

# Mock all external dependencies before any imports
# This prevents ImportError and allows tests to run in isolation


# Store references to prevent accidental mocking
_BUILTIN_MODULES = {
    "queue": queue,
    "logging": logging,
    "asyncio": asyncio,
    "threading": threading,
    "time": time,
}


def ensure_builtins_not_mocked():
    """
    Restores original Python built-in modules if they have been accidentally mocked during testing.

    This function checks for mocked versions of critical built-in modules and replaces them with their original references. It also reloads the logging module if it was mocked to ensure proper logging functionality is maintained.
    """
    for name, module in _BUILTIN_MODULES.items():
        if name in sys.modules and hasattr(sys.modules[name], "_mock_name"):
            # Restore the original module if it was mocked
            sys.modules[name] = module

    # Extra protection for logging system - but DON'T reload it!
    # Reloading logging can cause system freezes and deadlocks
    import logging

    if hasattr(logging, "_mock_name"):
        # If logging got mocked, restore from our saved reference instead of reloading
        sys.modules["logging"] = _BUILTIN_MODULES["logging"]


# Mock Meshtastic modules comprehensively
meshtastic_mock = MagicMock()
sys.modules["meshtastic"] = meshtastic_mock
sys.modules["meshtastic.protobuf"] = MagicMock()
sys.modules["meshtastic.protobuf.portnums_pb2"] = MagicMock()
sys.modules["meshtastic.protobuf.portnums_pb2"].PortNum = MagicMock()
sys.modules["meshtastic.protobuf.portnums_pb2"].PortNum.DETECTION_SENSOR_APP = 1
sys.modules["meshtastic.protobuf.mesh_pb2"] = MagicMock()
sys.modules["meshtastic.ble_interface"] = MagicMock()
sys.modules["meshtastic.serial_interface"] = MagicMock()
sys.modules["meshtastic.tcp_interface"] = MagicMock()
sys.modules["meshtastic.mesh_interface"] = MagicMock()

# Set up meshtastic constants
meshtastic_mock.BROADCAST_ADDR = "^all"

# Mock Matrix-nio modules comprehensively
nio_mock = MagicMock()
sys.modules["nio"] = nio_mock
sys.modules["nio.events"] = MagicMock()
sys.modules["nio.events.room_events"] = MagicMock()


# Create proper mock classes for nio that can be used with isinstance()
class MockMatrixRoom:
    pass


class MockReactionEvent:
    pass


class MockRoomMessageEmote:
    pass


class MockRoomMessageNotice:
    pass


class MockRoomMessageText:
    pass


class MockWhoamiError(Exception):
    """Mock WhoamiError that inherits from Exception for isinstance checks."""

    def __init__(self, message="Whoami error"):
        super().__init__(message)
        self.message = message


# Mock specific nio classes that are imported directly
nio_mock.AsyncClient = MagicMock()
nio_mock.AsyncClientConfig = MagicMock()
nio_mock.MatrixRoom = MockMatrixRoom
nio_mock.ReactionEvent = MockReactionEvent
nio_mock.RoomMessageEmote = MockRoomMessageEmote
nio_mock.RoomMessageNotice = MockRoomMessageNotice
nio_mock.RoomMessageText = MockRoomMessageText
nio_mock.UploadResponse = MagicMock()
nio_mock.WhoamiError = MockWhoamiError

# Mock RoomMemberEvent from nio.events.room_events
sys.modules["nio.events.room_events"].RoomMemberEvent = MagicMock()


# Mock PIL/Pillow
# Create proper PIL mock classes that work with real imports
class MockPILImage:
    """Mock PIL Image class that can be used as a spec."""

    def save(self, *args, **kwargs):
        """Mock save method for PIL Image."""
        pass


# Create a mock that allows attribute access like the real PIL module
pil_mock = MagicMock()
pil_image_mock = MagicMock()
pil_image_mock.Image = MockPILImage
pil_imagedraw_mock = MagicMock()

sys.modules["PIL"] = pil_mock
sys.modules["PIL.Image"] = pil_image_mock
sys.modules["PIL.ImageDraw"] = pil_imagedraw_mock

# Also set attributes on the main PIL mock for direct access
pil_mock.Image = pil_image_mock
pil_mock.ImageDraw = pil_imagedraw_mock

# Mock other external dependencies (but avoid Python built-ins)
# Mock certifi with proper where() function
certifi_mock = MagicMock()
certifi_mock.where.return_value = "/fake/cert/path.pem"
sys.modules["certifi"] = certifi_mock


# Don't mock ssl module - it can interfere with logging and other system components
# Instead, we'll mock ssl.create_default_context at the test level when needed
# Create proper exception class for serial
class SerialException(Exception):
    """Mock SerialException for testing."""

    pass


# Create serial module with proper exception
serial_mock = MagicMock()
serial_mock.SerialException = SerialException
sys.modules["serial"] = serial_mock
sys.modules["serial.tools"] = MagicMock()
sys.modules["serial.tools.list_ports"] = MagicMock()


# Create proper exception classes for bleak that inherit from Exception
class BleakError(Exception):
    """Mock BleakError exception for testing."""

    pass


class BleakDBusError(BleakError):
    """Mock BleakDBusError exception for testing."""

    pass


# Create a proper module-like object for bleak.exc
class BleakExcModule:
    BleakError = BleakError
    BleakDBusError = BleakDBusError


sys.modules["bleak"] = MagicMock()
sys.modules["bleak.exc"] = BleakExcModule()

# Also add the exceptions to the main bleak module for direct import
sys.modules["bleak"].BleakError = BleakError
sys.modules["bleak"].BleakDBusError = BleakDBusError
sys.modules["pubsub"] = MagicMock()
sys.modules["matplotlib"] = MagicMock()
sys.modules["matplotlib.pyplot"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["markdown"] = MagicMock()
sys.modules["haversine"] = MagicMock()
sys.modules["schedule"] = MagicMock()
sys.modules["platformdirs"] = MagicMock()
sys.modules["py_staticmaps"] = MagicMock()


# Create proper mock classes for s2sphere
class MockLatLng:
    """Mock LatLng class for s2sphere."""

    @classmethod
    def from_degrees(cls, lat, lng):
        return cls()


class MockLatLngRect:
    """Mock LatLngRect class for s2sphere."""

    @classmethod
    def from_point(cls, point):
        return cls()


class MockS2Module:
    LatLng = MockLatLng
    LatLngRect = MockLatLngRect


sys.modules["s2sphere"] = MockS2Module()

# Don't mock Rich at all - it can interfere with logging handlers
# Rich is optional and tests should work without it
# If Rich is needed for specific tests, mock it at the test level


@pytest.fixture(autouse=True)
def meshtastic_loop_safety(monkeypatch):
    """
    Module-scoped fixture to ensure the event loop in meshtastic_utils is
    properly managed and prevent AsyncMock pollution.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setattr(mu, "event_loop", loop)

    yield loop

    # Teardown: Clean up the loop
    try:
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(autouse=True)
def reset_plugin_loader_cache():
    """
    Reset plugin loader caches between tests to prevent AsyncMock pollution.

    This fixture ensures that cached plugin instances or callables don't
    leak between tests, which can cause unawaited AsyncMock warnings.
    """
    import mmrelay.plugin_loader as pl
    pl._reset_caches_for_tests()
    yield
    pl._reset_caches_for_tests()


@pytest.fixture(autouse=True)
def cleanup_asyncmock_objects():
    """
    Clean up AsyncMock objects between tests to prevent warnings.

    This fixture forces garbage collection after each test to ensure
    AsyncMock objects are cleaned up promptly, preventing "never awaited"
    warnings when they are garbage collected during other tests.
    """
    yield

    # Force garbage collection to clean up any AsyncMock objects
    import gc
    gc.collect()


@pytest.fixture(autouse=True)
def mock_submit_coro(monkeypatch):
    """
    Mock the _submit_coro function to prevent actual async execution in tests.

    This prevents AsyncMock warnings by ensuring coroutines are handled
    properly in the test environment.
    """
    import inspect
    import asyncio

    def mock_submit(coro, loop=None):
        """Mock implementation that properly handles AsyncMock coroutines."""
        if not inspect.iscoroutine(coro):  # Not a coroutine
            return None

        # For AsyncMock coroutines, we need to actually await them to get the result
        # and prevent "never awaited" warnings, while also triggering any side effects
        temp_loop = asyncio.new_event_loop()
        try:
            result = temp_loop.run_until_complete(coro)
            future = Future()
            future.set_result(result)
            return future
        except Exception as e:
            future = Future()
            future.set_exception(e)
            return future
        finally:
            temp_loop.close()

    monkeypatch.setattr(mu, "_submit_coro", mock_submit)
    yield


@pytest.fixture
def done_future():
    asyncio.get_event_loop()
    f = Future()
    f.set_result(None)
    return f


# Ensure built-in modules are not accidentally mocked
ensure_builtins_not_mocked()
