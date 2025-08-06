#!/usr/bin/env python3
"""
Test script to verify E2EE login functionality.
"""

import asyncio
import sys
import os
import ssl
import certifi

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from nio import AsyncClient, AsyncClientConfig

async def test_basic_matrix_connection():
    """Test basic Matrix connection to see what's happening."""
    try:
        print("Testing basic Matrix connection...")

        # Test with matrix.org first (more reliable)
        homeserver = "https://matrix.org"
        username = "@testuser:matrix.org"

        # Create SSL context and client config for E2EE
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        client_config = AsyncClientConfig(
            store_sync_tokens=True, encryption_enabled=True
        )

        # Initialize client with E2EE support
        client = AsyncClient(
            homeserver=homeserver,
            user=username,
            config=client_config,
            ssl=ssl_context,
        )

        print(f"Created client for {username} at {homeserver}")
        print(f"Client config: encryption_enabled={client_config.encryption_enabled}")

        # Try to get server info first
        try:
            print("Attempting login with longer timeout...")
            response = await asyncio.wait_for(
                client.login("fake_password"),
                timeout=120.0  # 2 minute timeout
            )
            print(f"Login response: {response}")
            print(f"Response type: {type(response)}")
            if hasattr(response, '__dict__'):
                print(f"Response attributes: {response.__dict__}")
        except asyncio.TimeoutError:
            print("Login timed out after 2 minutes - server may be slow or unreachable")
        except Exception as e:
            print(f"Login error (expected): {e}")
            print(f"Error type: {type(e)}")
            if hasattr(e, 'message'):
                print(f"Error message: {e.message}")
            if hasattr(e, 'status_code'):
                print(f"Status code: {e.status_code}")

        await client.close()

    except Exception as e:
        print(f"Connection error: {e}")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    asyncio.run(test_basic_matrix_connection())
