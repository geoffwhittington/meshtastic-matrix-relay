#!/usr/bin/env python3
"""
E2EE Test Runner

Quick test runner for E2EE encryption tests that can be run without full pytest setup.
Provides immediate feedback on encryption behavior.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tests.test_e2ee_encryption import (
    E2EETestFramework, 
    E2EEDiagnosticTools, 
    E2EEDebugUtilities,
    MockEncryptedRoom,
    MockUnencryptedRoom
)


async def test_basic_encryption_parameters():
    """Test basic encryption parameter handling"""
    print("🔍 Testing basic encryption parameters...")
    
    framework = E2EETestFramework()
    
    # Test encrypted room detection
    encrypted_room = MockEncryptedRoom("!test:example.org", encrypted=True)
    unencrypted_room = MockUnencryptedRoom("!test2:example.org")
    
    assert encrypted_room.encrypted == True, "Encrypted room should be detected"
    assert unencrypted_room.encrypted == False, "Unencrypted room should be detected"
    
    print("✅ Room encryption detection works")
    
    # Test mock client creation
    mock_client = framework.create_mock_client()
    assert mock_client.device_id == "TEST_DEVICE_ID", "Mock client should have device ID"
    assert len(mock_client.rooms) == 2, "Mock client should have test rooms"
    
    print("✅ Mock client creation works")
    return True


async def test_room_send_parameters():
    """Test that room_send is called with correct parameters"""
    print("🔍 Testing room_send parameter verification...")
    
    framework = E2EETestFramework()
    mock_client = framework.create_mock_client()
    
    # Simulate a room_send call
    await mock_client.room_send(
        room_id="!test:example.org",
        message_type="m.room.message",
        content={"msgtype": "m.text", "body": "Test"},
        ignore_unverified_devices=True
    )
    
    # Verify parameters
    call_args, kwargs = framework.verify_encryption_parameters(mock_client, expected_ignore_unverified=True)
    
    print("✅ room_send parameter verification works")
    print(f"   Called with: {kwargs}")
    return True


async def test_client_diagnostic_tools():
    """Test diagnostic tools for client inspection"""
    print("🔍 Testing diagnostic tools...")
    
    framework = E2EETestFramework()
    mock_client = framework.create_mock_client()
    
    # Test client state inspection
    state = E2EEDiagnosticTools.inspect_client_state(mock_client)
    
    assert state["device_id"] == "TEST_DEVICE_ID", "Should detect device ID"
    assert state["rooms_count"] == 2, "Should count rooms correctly"
    assert len(state["encrypted_rooms"]) == 1, "Should detect encrypted rooms"
    assert len(state["unencrypted_rooms"]) == 1, "Should detect unencrypted rooms"
    
    print("✅ Client state inspection works")
    print(f"   State: {state}")
    
    # Test prerequisite verification
    checks = E2EEDiagnosticTools.verify_e2ee_prerequisites(mock_client)
    
    assert checks["has_device_id"] == True, "Should detect device ID"
    assert checks["has_user_id"] == True, "Should detect user ID"
    
    print("✅ Prerequisite verification works")
    print(f"   Checks: {checks}")
    return True


async def run_all_tests():
    """Run all quick tests"""
    print("🚀 Running E2EE Quick Tests")
    print("=" * 50)
    
    tests = [
        ("Basic Encryption Parameters", test_basic_encryption_parameters),
        ("Room Send Parameters", test_room_send_parameters),
        ("Diagnostic Tools", test_client_diagnostic_tools),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\n📋 {test_name}")
            print("-" * 30)
            result = await test_func()
            results.append((test_name, "PASS", None))
            print(f"✅ {test_name}: PASSED")
        except Exception as e:
            results.append((test_name, "FAIL", str(e)))
            print(f"❌ {test_name}: FAILED - {e}")
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    
    for test_name, status, error in results:
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{status_icon} {test_name}: {status}")
        if error:
            print(f"   Error: {error}")
    
    print(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed!")
        return False


def create_real_client_diagnostic():
    """Create a diagnostic function for real Matrix client"""
    print("\n🔧 REAL CLIENT DIAGNOSTIC HELPER")
    print("=" * 50)
    print("To diagnose a real Matrix client, use this code:")
    print()
    print("```python")
    print("from tests.test_e2ee_encryption import E2EEDebugUtilities")
    print("from mmrelay.matrix_utils import matrix_client")
    print()
    print("# After MMRelay connects:")
    print("if matrix_client:")
    print("    diagnosis = await E2EEDebugUtilities.diagnose_client_encryption_state(matrix_client)")
    print("    print('Client Diagnosis:', diagnosis)")
    print("```")
    print()
    print("This will show:")
    print("- Client E2EE state")
    print("- Room encryption status")
    print("- Missing prerequisites")
    print("- Recommendations")


if __name__ == "__main__":
    print("E2EE Test Runner")
    print("================")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python test_e2ee_runner.py           # Run all quick tests")
        print("  python test_e2ee_runner.py --help    # Show this help")
        print("  python test_e2ee_runner.py --diag    # Show diagnostic helper")
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--diag":
        create_real_client_diagnostic()
        sys.exit(0)
    
    # Run tests
    success = asyncio.run(run_all_tests())
    
    print("\n🔧 NEXT STEPS:")
    print("1. Run full pytest suite: python -m pytest tests/test_e2ee_encryption.py -v")
    print("2. Use diagnostic helper on real client (see --diag)")
    print("3. Check MMRelay logs for room encryption status")
    
    create_real_client_diagnostic()
    
    sys.exit(0 if success else 1)
