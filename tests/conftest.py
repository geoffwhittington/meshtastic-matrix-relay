"""
Pytest configuration and fixtures for MMRelay tests.

This file sets up comprehensive mocking for external dependencies
to ensure tests can run without requiring actual hardware or network connections.
"""

import sys
from unittest.mock import MagicMock

# Mock all external dependencies before any imports
# This prevents ImportError and allows tests to run in isolation

# Preserve references to built-in modules that should NOT be mocked
import queue
import logging
import asyncio
import threading
import time

# Store references to prevent accidental mocking
_BUILTIN_MODULES = {
    'queue': queue,
    'logging': logging,
    'asyncio': asyncio,
    'threading': threading,
    'time': time,
}

def ensure_builtins_not_mocked():
    """Ensure that Python built-in modules are not accidentally mocked."""
    for name, module in _BUILTIN_MODULES.items():
        if name in sys.modules and hasattr(sys.modules[name], '_mock_name'):
            # Restore the original module if it was mocked
            sys.modules[name] = module

    # Extra protection for logging system
    import logging
    if hasattr(logging, '_mock_name'):
        # If logging itself got mocked, restore it
        import importlib
        importlib.reload(logging)

# Mock Meshtastic modules comprehensively
meshtastic_mock = MagicMock()
sys.modules['meshtastic'] = meshtastic_mock
sys.modules['meshtastic.protobuf'] = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'].PortNum = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'].PortNum.DETECTION_SENSOR_APP = 1
sys.modules['meshtastic.protobuf.mesh_pb2'] = MagicMock()
sys.modules['meshtastic.ble_interface'] = MagicMock()
sys.modules['meshtastic.serial_interface'] = MagicMock()
sys.modules['meshtastic.tcp_interface'] = MagicMock()

# Set up meshtastic constants
meshtastic_mock.BROADCAST_ADDR = "^all"

# Mock Matrix-nio modules comprehensively
nio_mock = MagicMock()
sys.modules['nio'] = nio_mock
sys.modules['nio.events'] = MagicMock()
sys.modules['nio.events.room_events'] = MagicMock()

# Mock specific nio classes that are imported directly
nio_mock.AsyncClient = MagicMock()
nio_mock.AsyncClientConfig = MagicMock()
nio_mock.MatrixRoom = MagicMock()
nio_mock.ReactionEvent = MagicMock()
nio_mock.RoomMessageEmote = MagicMock()
nio_mock.RoomMessageNotice = MagicMock()
nio_mock.RoomMessageText = MagicMock()
nio_mock.UploadResponse = MagicMock()
nio_mock.WhoamiError = MagicMock()

# Mock RoomMemberEvent from nio.events.room_events
sys.modules['nio.events.room_events'].RoomMemberEvent = MagicMock()

# Mock PIL/Pillow
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()

# Mock other external dependencies (but avoid Python built-ins)
sys.modules['certifi'] = MagicMock()
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()
sys.modules['bleak'] = MagicMock()
sys.modules['bleak.exc'] = MagicMock()
sys.modules['pubsub'] = MagicMock()
sys.modules['matplotlib'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['markdown'] = MagicMock()
sys.modules['haversine'] = MagicMock()
sys.modules['schedule'] = MagicMock()
sys.modules['platformdirs'] = MagicMock()
sys.modules['py_staticmaps'] = MagicMock()

# Mock Rich modules but preserve rich.logging for proper logging functionality
# Import the real rich module first to preserve its structure
try:
    import rich
    import rich.logging
    import rich.console
    # Keep the real rich module but mock specific components
    rich_mock = rich
    rich_mock.Console = MagicMock
    sys.modules['rich.console'] = MagicMock()
except ImportError:
    # If rich is not available, create a minimal mock that won't interfere with logging
    rich_mock = MagicMock()
    sys.modules['rich'] = rich_mock
    sys.modules['rich.console'] = MagicMock()
    # Create a minimal rich.logging mock that won't break the logging system
    rich_logging_mock = MagicMock()
    rich_logging_mock.RichHandler = MagicMock
    sys.modules['rich.logging'] = rich_logging_mock

# Ensure built-in modules are not accidentally mocked
ensure_builtins_not_mocked()
