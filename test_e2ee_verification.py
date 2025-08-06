#!/usr/bin/env python3
"""
E2EE Verification Test Script

This script helps verify that E2EE functionality is working correctly.
It tests the login process and shows how to verify encrypted messages.
"""

import asyncio
import sys
import os
import json

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mmrelay.matrix_utils import login_matrix_bot, connect_matrix
from mmrelay.config import get_base_dir

def check_e2ee_dependencies():
    """Check if E2EE dependencies are installed."""
    try:
        import olm
        import nio.crypto
        print("✅ E2EE dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ E2EE dependencies missing: {e}")
        print("Install with: pip install -r requirements-e2e.txt")
        return False

def check_credentials():
    """Check if credentials.json exists."""
    config_dir = get_base_dir()
    credentials_path = os.path.join(config_dir, "credentials.json")
    
    if os.path.exists(credentials_path):
        try:
            with open(credentials_path, 'r') as f:
                creds = json.load(f)
            print("✅ credentials.json found")
            print(f"   User: {creds.get('user_id', 'Unknown')}")
            print(f"   Server: {creds.get('homeserver', 'Unknown')}")
            print(f"   Device ID: {creds.get('device_id', 'Unknown')}")
            return True
        except Exception as e:
            print(f"❌ Error reading credentials.json: {e}")
            return False
    else:
        print("❌ credentials.json not found")
        print("   Run 'mmrelay --auth' to create credentials")
        return False

async def test_matrix_connection():
    """Test Matrix connection with E2EE."""
    try:
        print("\n🔄 Testing Matrix connection...")
        
        # Mock config for testing
        test_config = {
            'matrix': {
                'homeserver': 'https://matrix.org',
                'rooms': [{'id': '!test:matrix.org', 'meshtastic_channel': 0}],
                'bot_user_id': '@test:matrix.org'
            },
            'e2ee': {
                'enabled': True
            }
        }
        
        client = await connect_matrix(test_config)
        if client:
            print("✅ Matrix connection successful")
            print(f"   Client type: {type(client)}")
            print(f"   E2EE enabled: {hasattr(client, 'olm')}")
            await client.close()
            return True
        else:
            print("❌ Matrix connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Matrix connection error: {e}")
        return False

def show_encryption_verification_guide():
    """Show how to verify messages are encrypted."""
    print("\n📋 How to verify E2EE is working:")
    print("1. Set up two Matrix clients (e.g., Element on phone and desktop)")
    print("2. Create an encrypted room and invite your mmrelay bot")
    print("3. Send a message from Meshtastic - it should appear encrypted in Matrix")
    print("4. Send a message from Matrix - it should appear on Meshtastic")
    print("5. Check Matrix client logs for 'encrypted' or 'MegolmEvent' messages")
    print("6. Verify the room shows a lock icon in Matrix clients")
    
    print("\n🔍 Debugging tips:")
    print("- Check mmrelay logs for 'E2EE', 'encrypted', or 'MegolmEvent' messages")
    print("- Verify the room is actually encrypted (lock icon in Matrix client)")
    print("- Check that ignore_unverified_devices=True is working")
    print("- Look for 'Device store' messages in logs")

async def main():
    """Main test function."""
    print("🔐 MMRelay E2EE Verification Test")
    print("=" * 40)
    
    # Check dependencies
    if not check_e2ee_dependencies():
        return
    
    # Check credentials
    has_creds = check_credentials()
    
    # Test connection if we have credentials
    if has_creds:
        await test_matrix_connection()
    
    # Show verification guide
    show_encryption_verification_guide()
    
    print("\n✨ E2EE verification complete!")
    if not has_creds:
        print("Next step: Run 'mmrelay --auth' to set up E2EE credentials")

if __name__ == "__main__":
    asyncio.run(main())
