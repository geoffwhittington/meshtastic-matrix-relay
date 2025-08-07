#!/usr/bin/env python3
"""
E2EE Debug Utility

This utility can be used to debug E2EE issues in MMRelay by inspecting
the actual Matrix client state and providing detailed diagnostics.

Usage:
1. Start MMRelay normally
2. In another terminal, run: python debug_e2ee.py
3. This will connect and inspect the E2EE state
"""

import asyncio
import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from mmrelay.matrix_utils import connect_matrix
    from mmrelay.config import get_config
    from tests.test_e2ee_encryption import E2EEDebugUtilities
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class E2EEDebugger:
    """E2EE debugging utility"""
    
    def __init__(self):
        self.config = None
        self.client = None
    
    async def connect_and_diagnose(self):
        """Connect to Matrix and perform comprehensive E2EE diagnosis"""
        print("🔧 E2EE Debug Utility")
        print("=" * 50)
        
        # Load config
        print("📋 Loading configuration...")
        try:
            self.config = get_config()
            if not self.config:
                raise Exception("Could not load config")
            print("✅ Configuration loaded")
        except Exception as e:
            print(f"❌ Config error: {e}")
            return False
        
        # Connect to Matrix
        print("\n🔗 Connecting to Matrix...")
        try:
            self.client = await connect_matrix(self.config)
            if not self.client:
                raise Exception("Failed to connect")
            print("✅ Matrix connection successful")
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
        
        # Perform diagnosis
        await self.diagnose_client_state()
        await self.diagnose_room_encryption()
        await self.test_message_parameters()
        
        # Cleanup
        try:
            await self.client.close()
        except:
            pass
        
        return True
    
    async def diagnose_client_state(self):
        """Diagnose Matrix client E2EE state"""
        print("\n🔍 CLIENT E2EE STATE DIAGNOSIS")
        print("-" * 40)
        
        # Basic client info
        print("📊 Basic Client Information:")
        print(f"   User ID: {getattr(self.client, 'user_id', 'None')}")
        print(f"   Device ID: {getattr(self.client, 'device_id', 'None')}")
        print(f"   Access Token: {'***' if getattr(self.client, 'access_token', None) else 'None'}")
        print(f"   Store Path: {getattr(self.client, 'store_path', 'None')}")
        
        # E2EE configuration
        print("\n🔐 E2EE Configuration:")
        if hasattr(self.client, 'config') and self.client.config:
            config = self.client.config
            print(f"   Encryption Enabled: {getattr(config, 'encryption_enabled', 'Unknown')}")
            print(f"   Store Sync Tokens: {getattr(config, 'store_sync_tokens', 'Unknown')}")
        else:
            print("   No client config found")
        
        # E2EE capabilities
        print("\n🛠️  E2EE Capabilities:")
        print(f"   Should Upload Keys: {getattr(self.client, 'should_upload_keys', 'Unknown')}")
        print(f"   Has OLM: {hasattr(self.client, 'olm')}")
        
        if hasattr(self.client, 'olm') and self.client.olm:
            print(f"   OLM Account: {bool(getattr(self.client.olm, 'account', None))}")
            print(f"   Device Store: {bool(getattr(self.client, 'device_store', None))}")
        
        # Store information
        store_path = getattr(self.client, 'store_path', None)
        if store_path:
            store_exists = Path(store_path).exists()
            print(f"   Store Directory Exists: {store_exists}")
            if store_exists:
                store_files = list(Path(store_path).glob("*"))
                print(f"   Store Files: {len(store_files)} files")
    
    async def diagnose_room_encryption(self):
        """Diagnose room encryption state"""
        print("\n🏠 ROOM ENCRYPTION DIAGNOSIS")
        print("-" * 40)
        
        rooms = getattr(self.client, 'rooms', {})
        print(f"📊 Room Summary: {len(rooms)} total rooms")
        
        if not rooms:
            print("⚠️  No rooms found - performing sync to populate rooms...")
            try:
                await asyncio.wait_for(
                    self.client.sync(timeout=10000, full_state=True),
                    timeout=15.0
                )
                rooms = getattr(self.client, 'rooms', {})
                print(f"   After sync: {len(rooms)} rooms found")
            except Exception as e:
                print(f"   Sync failed: {e}")
                return
        
        encrypted_rooms = []
        unencrypted_rooms = []
        unknown_rooms = []
        
        print("\n🔍 Room Analysis:")
        for room_id, room in rooms.items():
            encrypted = getattr(room, 'encrypted', 'unknown')
            display_name = getattr(room, 'display_name', 'Unknown')
            member_count = getattr(room, 'member_count', 'Unknown')
            
            print(f"   Room: {display_name[:30]}")
            print(f"      ID: {room_id}")
            print(f"      Encrypted: {encrypted}")
            print(f"      Members: {member_count}")
            print(f"      Type: {type(room).__name__}")
            
            if encrypted is True:
                encrypted_rooms.append(room_id)
            elif encrypted is False:
                unencrypted_rooms.append(room_id)
            else:
                unknown_rooms.append(room_id)
            
            print()
        
        print("📈 Encryption Summary:")
        print(f"   Encrypted rooms: {len(encrypted_rooms)}")
        print(f"   Unencrypted rooms: {len(unencrypted_rooms)}")
        print(f"   Unknown encryption: {len(unknown_rooms)}")
        
        if encrypted_rooms:
            print(f"\n✅ Found {len(encrypted_rooms)} encrypted room(s) - E2EE should work")
        else:
            print(f"\n⚠️  No encrypted rooms found - this may be the issue!")
    
    async def test_message_parameters(self):
        """Test message sending parameter logic"""
        print("\n📤 MESSAGE SENDING PARAMETER TEST")
        print("-" * 40)
        
        rooms = getattr(self.client, 'rooms', {})
        if not rooms:
            print("❌ No rooms available for testing")
            return
        
        # Test with different room types
        test_cases = []
        
        # Find encrypted room
        for room_id, room in rooms.items():
            if getattr(room, 'encrypted', False):
                test_cases.append(('Encrypted Room', room_id, room))
                break
        
        # Find unencrypted room
        for room_id, room in rooms.items():
            if getattr(room, 'encrypted', False) is False:
                test_cases.append(('Unencrypted Room', room_id, room))
                break
        
        # Test non-existent room
        test_cases.append(('Non-existent Room', '!fake:example.org', None))
        
        print("🧪 Testing parameter logic for different room types:")
        
        for test_name, room_id, room in test_cases:
            print(f"\n   {test_name}:")
            print(f"      Room ID: {room_id}")
            
            if room:
                encrypted = getattr(room, 'encrypted', 'unknown')
                print(f"      Room encrypted: {encrypted}")
            else:
                print(f"      Room: Not found in client.rooms")
                encrypted = 'unknown'
            
            # Simulate the current logic from matrix_relay
            # Current implementation always uses ignore_unverified_devices=True
            ignore_unverified = True
            
            print(f"      Would use ignore_unverified_devices: {ignore_unverified}")
            
            # Check if this matches expected behavior
            if room and getattr(room, 'encrypted', False):
                expected = True
                status = "✅ Correct" if ignore_unverified == expected else "❌ Wrong"
                print(f"      Expected for encrypted room: {expected} - {status}")
            else:
                print(f"      Current implementation always uses True")
    
    def generate_diagnosis_report(self):
        """Generate final diagnosis report"""
        print("\n📋 E2EE DIAGNOSIS REPORT")
        print("=" * 50)
        
        print("🔍 KEY FINDINGS:")
        print("1. Check if encrypted rooms are detected properly")
        print("2. Verify ignore_unverified_devices=True is used")
        print("3. Ensure full sync populates room encryption state")
        print("4. Confirm E2EE store and keys are properly loaded")
        
        print("\n💡 TROUBLESHOOTING STEPS:")
        print("1. If no encrypted rooms found:")
        print("   - Ensure full sync with full_state=True")
        print("   - Check if rooms are actually encrypted in Element")
        print("   - Verify client is properly joined to encrypted rooms")
        
        print("\n2. If rooms detected but messages not encrypted:")
        print("   - Check matrix-nio version compatibility")
        print("   - Verify E2EE store is properly loaded")
        print("   - Ensure device keys are uploaded")
        
        print("\n3. Compare with working matrix-nio-send:")
        print("   - Same AsyncClient configuration")
        print("   - Same ignore_unverified_devices=True")
        print("   - Same full sync before sending")
        
        print("\n🔧 NEXT STEPS:")
        print("1. Run: python test_e2ee_runner.py")
        print("2. Run: python test_e2ee_integration.py")
        print("3. Compare logs with matrix-nio-send behavior")
        print("4. Check Element for actual message encryption status")


async def main():
    """Main debug function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("E2EE Debug Utility")
        print("==================")
        print("Diagnoses E2EE issues in MMRelay by connecting to Matrix")
        print("and inspecting the client state.")
        print()
        print("Usage:")
        print("  python debug_e2ee.py        # Run E2EE diagnosis")
        print("  python debug_e2ee.py --help # Show this help")
        print()
        print("Requirements:")
        print("- Valid MMRelay configuration")
        print("- Matrix credentials (credentials.json)")
        print("- Network access to Matrix homeserver")
        return
    
    debugger = E2EEDebugger()
    success = await debugger.connect_and_diagnose()
    debugger.generate_diagnosis_report()
    
    if success:
        print("\n✅ Diagnosis completed successfully")
    else:
        print("\n❌ Diagnosis failed - check errors above")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
