"""
Test that all imports work correctly with mocking.

This test verifies that the mocking setup in conftest.py properly handles
all external dependencies and allows modules to be imported without errors.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_basic_imports():
    """Test that basic modules can be imported without errors."""
    # These should work with the mocking setup
    from mmrelay.message_queue import MessageQueue
    from mmrelay.matrix_utils import get_matrix_prefix, get_meshtastic_prefix
    
    # Test that the functions exist and are callable
    assert callable(get_matrix_prefix)
    assert callable(get_meshtastic_prefix)
    assert MessageQueue is not None


def test_external_dependencies_mocked():
    """Test that external dependencies are properly mocked."""
    import meshtastic
    import nio
    from PIL import Image
    
    # These should be MagicMock objects
    assert hasattr(meshtastic, 'BROADCAST_ADDR')
    assert hasattr(nio, 'AsyncClient')
    assert Image is not None


def test_prefix_functions():
    """Test the prefix functions with basic inputs."""
    from mmrelay.matrix_utils import get_matrix_prefix, get_meshtastic_prefix
    
    # Test meshtastic prefix
    config = {"meshtastic": {"prefix_enabled": True}}
    prefix = get_meshtastic_prefix(config, "TestUser")
    assert isinstance(prefix, str)
    
    # Test matrix prefix  
    matrix_config = {"matrix": {"prefix_enabled": True}}
    matrix_prefix = get_matrix_prefix(matrix_config, "TestLong", "TestShort", "TestMesh")
    assert isinstance(matrix_prefix, str)
