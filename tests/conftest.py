"""
Pytest configuration and fixtures for MMRelay tests.

This file sets up comprehensive mocking for external dependencies
to ensure tests can run without requiring actual hardware or network connections.
"""

import asyncio
import logging
import os

# Preserve references to built-in modules that should NOT be mocked
import queue
import sys
import tempfile
import threading
import time
from unittest.mock import MagicMock

import pytest

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

    # Extra protection for logging system
    import logging

    if hasattr(logging, "_mock_name"):
        # If logging itself got mocked, restore it
        import importlib

        importlib.reload(logging)


# Only mock external dependencies that would cause ImportError
# This allows actual code to execute while preventing import failures


# Mock Meshtastic modules only if they don't exist
# This prevents ImportError while allowing actual code execution
def setup_meshtastic_mocks():
    """Set up Meshtastic mocks only if modules aren't already available."""
    try:
        import meshtastic
        # If import succeeds, don't mock - use real module
        return
    except ImportError:
        # Only mock if import fails
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

def setup_nio_mocks():
    """Set up Matrix-nio mocks only if modules aren't already available."""
    try:
        import nio
        # If import succeeds, don't mock - use real module
        return
    except ImportError:
        # Only mock if import fails
        nio_mock = MagicMock()
        sys.modules["nio"] = nio_mock
        sys.modules["nio.events"] = MagicMock()
        sys.modules["nio.events.room_events"] = MagicMock()

        # Mock specific nio classes that are imported directly
        # Create proper mock classes that can be used with isinstance()
        class MockReactionEvent:
            pass

        class MockRoomMessageEmote:
            pass

        class MockRoomMessageText:
            pass

        class MockRoomMessageNotice:
            pass

        class MockMatrixRoom:
            pass

        class MockWhoamiError:
            def __init__(self, message="Whoami error"):
                """
                Initialize the MockWhoamiError with an optional error message.

                Parameters:
                    message (str): The error message to associate with the exception. Defaults to "Whoami error".
                """
                self.message = message

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

def setup_optional_dependency_mocks():
    """Set up mocks for optional dependencies that might not be installed."""
    # Mock PIL/Pillow only if not available
    try:
        import PIL
    except ImportError:
        sys.modules["PIL"] = MagicMock()
        sys.modules["PIL.Image"] = MagicMock()
        sys.modules["PIL.ImageDraw"] = MagicMock()

    # Mock serial only if not available
    try:
        import serial
    except ImportError:
        sys.modules["serial"] = MagicMock()
        sys.modules["serial.tools"] = MagicMock()
        sys.modules["serial.tools.list_ports"] = MagicMock()

    # Mock other optional dependencies
    optional_deps = ["certifi", "requests", "markdown", "haversine", "schedule", "py_staticmaps"]
    for dep in optional_deps:
        try:
            __import__(dep)
        except ImportError:
            sys.modules[dep] = MagicMock()


def setup_bleak_mocks():
    """Set up Bleak (Bluetooth) mocks only if not available."""
    try:
        import bleak
    except ImportError:
        # Create proper exception classes for bleak that inherit from Exception
        class BleakError(Exception):
            """Mock BleakError exception for testing."""
            pass

        class BleakDBusError(BleakError):
            """Mock BleakDBusError exception for testing."""
            pass

        # Create a proper module-like object for bleak.exc
        class BleakExcModule:
            pass

        # Set the exception classes as attributes
        BleakExcModule.BleakError = BleakError
        BleakExcModule.BleakDBusError = BleakDBusError

        # Create main bleak module mock with exception classes
        bleak_module = MagicMock()
        bleak_module.BleakError = BleakError
        bleak_module.BleakDBusError = BleakDBusError

        sys.modules["bleak"] = bleak_module
        sys.modules["bleak.exc"] = BleakExcModule()

def setup_remaining_mocks():
    """Set up mocks for remaining dependencies."""
    # Mock matplotlib only if not available
    try:
        import matplotlib
    except ImportError:
        sys.modules["matplotlib"] = MagicMock()
        sys.modules["matplotlib.pyplot"] = MagicMock()

    # Mock pubsub only if not available
    try:
        import pubsub
    except ImportError:
        sys.modules["pubsub"] = MagicMock()

    # Mock platformdirs only if not available
    try:
        import platformdirs
    except ImportError:
        sys.modules["platformdirs"] = MagicMock()

def setup_rich_mocks():
    """Set up Rich mocks while preserving logging functionality."""
    try:
        import rich
        import rich.console
        import rich.logging
        # Keep the real rich module - don't mock if available
    except ImportError:
        # If rich is not available, create a minimal mock that won't interfere with logging
        rich_mock = MagicMock()
        sys.modules["rich"] = rich_mock
        sys.modules["rich.console"] = MagicMock()
        # Create a minimal rich.logging mock that won't break the logging system
        rich_logging_mock = MagicMock()
        rich_logging_mock.RichHandler = MagicMock
        sys.modules["rich.logging"] = rich_logging_mock


# Initialize all mocks
setup_meshtastic_mocks()
setup_nio_mocks()
setup_optional_dependency_mocks()
setup_bleak_mocks()
setup_remaining_mocks()
setup_rich_mocks()

# Ensure built-in modules are not accidentally mocked
ensure_builtins_not_mocked()


def pytest_addoption(parser):
    """
    Adds the --runslow command-line option to pytest to enable running tests marked as slow.

    Parameters:
        parser: The pytest parser object used to add custom command-line options.
    """
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    """
    Registers the 'slow' marker with pytest to label tests that are slow to run.
    """
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    """
    Skips tests marked as 'slow' unless the --runslow option is specified.

    Tests with the 'slow' marker are automatically skipped during collection unless the user provides the --runslow command-line option.
    """
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


# Test fixtures for configuration and temporary resources


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Pytest fixture that sets up an isolated test environment using a temporary configuration directory.
    
    This fixture overrides the MMRelay configuration directory to a temporary location, writes a test configuration file, and ensures cleanup after tests complete. It prevents tests from modifying or interfering with real user configuration files.
    """
    import tempfile
    import mmrelay.config
    import shutil

    # Create a temporary directory for test configs
    temp_dir = tempfile.mkdtemp(prefix="mmrelay_test_")

    try:
        # Store original custom_data_dir
        original_custom_data_dir = mmrelay.config.custom_data_dir

        # Set custom_data_dir to our temp directory to prevent writing to real user dirs
        mmrelay.config.custom_data_dir = temp_dir

        # Create test config content
        test_config = """# Test configuration for MMRelay
matrix:
  homeserver: "https://matrix.example.org"
  username: "@testbot:example.org"
  password: "test_password"

meshtastic:
  connection_type: "serial"
  serial_port: "/dev/ttyUSB0"
  meshnet_name: "TestMesh"

matrix_rooms:
  general:
    id: "!testroom:example.org"
    meshtastic_channel: 0

plugins:
  debug:
    active: true
"""

        # Create config file in temp directory
        config_path = os.path.join(temp_dir, "config.yaml")
        try:
            with open(config_path, "w") as f:
                f.write(test_config)
            print(f"Created test config at {config_path}")
        except (OSError, PermissionError):
            print("Could not create test config file")

        # Run tests
        yield

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Restore original custom_data_dir
        mmrelay.config.custom_data_dir = original_custom_data_dir


@pytest.fixture
def temp_dir():
    """
    Provide a temporary directory path for use during a test, ensuring automatic cleanup after the test finishes.
    
    Yields:
        str: Path to the temporary directory.
    """
    with tempfile.TemporaryDirectory() as temp_path:
        yield temp_path


@pytest.fixture
def temp_db():
    """
    Yields the path to a temporary database file for use in tests, ensuring the file is deleted after the test completes.

    Returns:
        db_path (str): The filesystem path to the temporary database file.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    yield db_path

    # Clean up
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_config():
    """
    Return a mock configuration dictionary representing typical MMRelay settings for testing purposes.
    
    Returns:
        dict: Mock configuration data including Matrix, Meshtastic, room, and plugin settings.
    """
    return {
        "matrix": {
            "homeserver": "https://matrix.example.org",
            "username": "@testbot:example.org",
            "password": "test_password",
        },
        "meshtastic": {
            "connection_type": "serial",
            "serial_port": "/dev/ttyUSB0",
            "meshnet_name": "TestMesh",
        },
        "matrix_rooms": {
            "general": {"id": "!testroom:example.org", "meshtastic_channel": 0}
        },
        "plugins": {"debug": {"active": True}},
    }


@pytest.fixture(autouse=True)
def cleanup_async_objects():
    """
    Automatically cleans up unawaited coroutines and AsyncMock objects after each test to prevent resource warnings and side effects.
    """
    yield  # Run the test

    # Clean up any remaining coroutines
    import gc
    from unittest.mock import AsyncMock

    try:
        # Get all objects in memory
        for obj in gc.get_objects():
            # Close any coroutines that weren't awaited
            if asyncio.iscoroutine(obj):
                try:
                    obj.close()
                except:
                    pass
            # Clean up AsyncMock objects
            elif isinstance(obj, AsyncMock):
                try:
                    # Reset the AsyncMock to clear any pending coroutines
                    obj.reset_mock()
                except:
                    pass
    except:
        pass

    # Force garbage collection to clean up any remaining objects
    gc.collect()
