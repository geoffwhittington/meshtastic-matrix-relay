#!/usr/bin/env python3
"""
Test script for prefix customization functionality.
Demonstrates the new configurable prefix formats for both directions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mmrelay.matrix_utils import get_meshtastic_prefix, get_matrix_prefix


def test_matrix_to_meshtastic_prefixes():
    """Test Matrix to Meshtastic prefix customization."""
    print("=== Matrix → Meshtastic Prefix Tests ===\n")
    
    # Test data
    short_name = "Alice"
    full_name = "Alice Smith"
    
    # Test 1: Default configuration (enabled)
    config1 = {"meshtastic": {"prefix_enabled": True}}
    prefix1 = get_meshtastic_prefix(config1, short_name, full_name)
    print(f"Default format: '{prefix1}Hello world'")
    
    # Test 2: Disabled prefixes
    config2 = {"meshtastic": {"prefix_enabled": False}}
    prefix2 = get_meshtastic_prefix(config2, short_name, full_name)
    print(f"Disabled: '{prefix2}Hello world'")
    
    # Test 3: Variable length truncation
    config3 = {"meshtastic": {"prefix_enabled": True, "prefix_format": "{name3}[M]: "}}
    prefix3 = get_meshtastic_prefix(config3, full_name)
    print(f"3-char name: '{prefix3}Hello world'")

    # Test 4: Custom format with full name
    config4 = {"meshtastic": {"prefix_enabled": True, "prefix_format": "[{name}]: "}}
    prefix4 = get_meshtastic_prefix(config4, full_name)
    print(f"Full name brackets: '{prefix4}Hello world'")

    # Test 5: Custom format with user ID
    config5 = {"meshtastic": {"prefix_enabled": True, "prefix_format": "{name8}> "}}
    prefix5 = get_meshtastic_prefix(config5, full_name, "@alice:matrix.org")
    print(f"8-char prompt: '{prefix5}Hello world'")
    
    # Test 6: Invalid format (should fallback)
    config6 = {"meshtastic": {"prefix_enabled": True, "prefix_format": "{invalid}: "}}
    prefix6 = get_meshtastic_prefix(config6, full_name)
    print(f"Invalid format (fallback): '{prefix6}Hello world'")
    
    print()


def test_meshtastic_to_matrix_prefixes():
    """Test Meshtastic to Matrix prefix customization."""
    print("=== Meshtastic → Matrix Prefix Tests ===\n")

    # Test data
    longname = "Alice"
    shortname = "Ali"
    meshnet = "MyMeshNetwork"

    # Test 1: Default configuration (enabled)
    config1 = {"matrix": {"prefix_enabled": True}}
    prefix1 = get_matrix_prefix(config1, longname, shortname, meshnet)
    print(f"Default format: '{prefix1}Hello from mesh'")

    # Test 2: Disabled prefixes
    config2 = {"matrix": {"prefix_enabled": False}}
    prefix2 = get_matrix_prefix(config2, longname, shortname, meshnet)
    print(f"Disabled: '{prefix2}Hello from mesh'")

    # Test 3: Variable length truncation
    config3 = {"matrix": {"prefix_enabled": True, "prefix_format": "({long4}): "}}
    prefix3 = get_matrix_prefix(config3, longname, shortname, meshnet)
    print(f"4-char longname: '{prefix3}Hello from mesh'")

    # Test 4: Custom format with truncated mesh
    config4 = {"matrix": {"prefix_enabled": True, "prefix_format": "[{mesh6}] {short}: "}}
    prefix4 = get_matrix_prefix(config4, longname, shortname, meshnet)
    print(f"6-char mesh: '{prefix4}Hello from mesh'")

    # Test 5: Invalid format (should fallback)
    config5 = {"matrix": {"prefix_enabled": True, "prefix_format": "{invalid}: "}}
    prefix5 = get_matrix_prefix(config5, longname, shortname, meshnet)
    print(f"Invalid format (fallback): '{prefix5}Hello from mesh'")

    print()


def test_prefix_symmetry():
    """Test prefix symmetry scenarios."""
    print("=== Prefix Symmetry Tests ===\n")
    
    # Test scenario: Both directions disabled
    config_both_off = {
        "meshtastic": {"prefix_enabled": False},
        "matrix": {"prefix_enabled": False}
    }

    m2m_prefix = get_meshtastic_prefix(config_both_off, "Alice", "Alice Smith")
    mesh2m_prefix = get_matrix_prefix(config_both_off, "Bob", "Bob", "TestMesh")

    print("Both disabled:")
    print(f"  Matrix→Mesh: '{m2m_prefix}Hello'")
    print(f"  Mesh→Matrix: '{mesh2m_prefix}Hi there'")
    print()

    # Test scenario: Minimal custom formats
    config_minimal = {
        "meshtastic": {"prefix_enabled": True, "prefix_format": "{name4}: "},
        "matrix": {"prefix_enabled": True, "prefix_format": "{short}: "}
    }

    m2m_prefix = get_meshtastic_prefix(config_minimal, "Alice Smith")
    mesh2m_prefix = get_matrix_prefix(config_minimal, "Bob", "Bob", "TestMesh")

    print("Minimal symmetric:")
    print(f"  Matrix→Mesh: '{m2m_prefix}Hello'")
    print(f"  Mesh→Matrix: '{mesh2m_prefix}Hi there'")
    print()


def test_edge_cases():
    """Test edge cases and error handling."""
    print("=== Edge Case Tests ===\n")
    
    # Test with empty/None values
    config = {"meshtastic": {"prefix_enabled": True}, "matrix": {"prefix_enabled": True}}

    # Empty names
    prefix1 = get_meshtastic_prefix(config, "")
    prefix2 = get_matrix_prefix(config, "", "", "")
    print("Empty names:")
    print(f"  Matrix→Mesh: '{prefix1}message'")
    print(f"  Mesh→Matrix: '{prefix2}message'")
    print()

    # Very long names
    long_name = "VeryLongUserNameThatExceedsNormalLimits"
    prefix3 = get_meshtastic_prefix(config, long_name)
    prefix4 = get_matrix_prefix(config, long_name, long_name[:3], "VeryLongMeshNetworkName")
    print("Long names:")
    print(f"  Matrix→Mesh: '{prefix3}message'")
    print(f"  Mesh→Matrix: '{prefix4}message'")
    print()


if __name__ == "__main__":
    print("Testing Prefix Customization System\n")
    
    test_matrix_to_meshtastic_prefixes()
    test_meshtastic_to_matrix_prefixes()
    test_prefix_symmetry()
    test_edge_cases()
    
    print("All tests completed!")
