#!/usr/bin/env python3
"""
Test script to debug tchncs.de connection issues with detailed logging
"""

import asyncio
import logging
import ssl
import sys

import aiohttp
import certifi
from nio import AsyncClient, AsyncClientConfig, LoginError

# Configure comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Enable all relevant loggers
loggers = [
    "nio",
    "nio.client",
    "nio.http_client",
    "nio.api",
    "aiohttp",
    "aiohttp.client",
    "aiohttp.connector",
    "asyncio",
]

for logger_name in loggers:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


async def test_connection():
    """Test connection to tchncs.de and matrix.org with detailed logging"""

    # Test both servers
    test_servers = [
        ("https://tchncs.de", "@testuser:matrix.tchncs.de"),
        ("https://matrix.org", "@testuser:matrix.org"),
    ]

    for homeserver, username in test_servers:
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING SERVER: {homeserver}")
        logger.info(f"{'='*60}")
        await test_server(homeserver, username)


async def test_server(homeserver, username):
    """Test a specific server"""
    password = "test_password_not_real"  # nosec B105 - Test password only

    logger.info(f"Starting connection test to {homeserver}")

    # Test 1: Server discovery
    logger.info("=== TEST 1: Server Discovery ===")
    temp_client = AsyncClient(homeserver, "")
    try:
        logger.info("Calling discovery_info()...")
        discovery_response = await asyncio.wait_for(
            temp_client.discovery_info(), timeout=30.0
        )
        logger.info(f"Discovery response type: {type(discovery_response)}")
        logger.info(f"Discovery response: {discovery_response}")

        if hasattr(discovery_response, "homeserver_url"):
            actual_homeserver = discovery_response.homeserver_url
            logger.info(f"Discovered homeserver: {actual_homeserver}")
            homeserver = actual_homeserver

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
    finally:
        await temp_client.close()

    # Test 1.5: Direct HTTP test to Matrix API
    logger.info("=== TEST 1.5: Direct HTTP test to Matrix API ===")
    try:
        async with aiohttp.ClientSession() as session:
            logger.info("Testing /_matrix/client/versions endpoint directly...")
            async with session.get(
                f"{homeserver}/_matrix/client/versions",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                logger.info(f"HTTP status: {resp.status}")
                logger.info(f"HTTP headers: {dict(resp.headers)}")
                text = await resp.text()
                logger.info(f"Response body: {text[:200]}...")
    except asyncio.TimeoutError:
        logger.error("Direct HTTP request timed out")
    except Exception as e:
        logger.error(f"Direct HTTP request failed: {e}")

    # Test 2: Connection with default SSL
    logger.info("=== TEST 2: Connection with default SSL ===")
    client_config = AsyncClientConfig(store_sync_tokens=True, encryption_enabled=True)

    client = AsyncClient(
        homeserver,
        username,
        device_id="test-device",
        config=client_config,
        ssl=None,  # Default SSL
    )

    try:
        logger.info(f"Attempting login to {homeserver} as {username}")

        # Test API versions first
        logger.info("Testing API versions endpoint...")
        try:
            versions_response = await asyncio.wait_for(client.versions(), timeout=10.0)
            logger.info(f"API versions response: {versions_response}")
        except asyncio.TimeoutError:
            logger.error("API versions endpoint timed out")
        except Exception as e:
            logger.error(f"API versions error: {e}")

        logger.info("Calling client.login()...")

        # Add timeout to see where it hangs
        login_response = await asyncio.wait_for(
            client.login(password=password, device_name="test-device"), timeout=30.0
        )

        logger.info(f"Login response type: {type(login_response)}")
        logger.info(f"Login response: {login_response}")

    except asyncio.TimeoutError:
        logger.error("Login timed out after 30 seconds")
    except LoginError as e:
        logger.info(f"Login failed as expected: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await client.close()

    # Test 3: Connection with certifi SSL
    logger.info("=== TEST 3: Connection with certifi SSL ===")
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    client2 = AsyncClient(
        homeserver,
        username,
        device_id="test-device-2",
        config=client_config,
        ssl=ssl_context,  # Certifi SSL
    )

    try:
        logger.info(f"Attempting login to {homeserver} as {username} with certifi SSL")
        logger.info("Calling client.login()...")

        login_response = await asyncio.wait_for(
            client2.login(password=password, device_name="test-device-2"), timeout=30.0
        )

        logger.info(f"Login response type: {type(login_response)}")
        logger.info(f"Login response: {login_response}")

    except asyncio.TimeoutError:
        logger.error("Login timed out after 30 seconds")
    except LoginError as e:
        logger.info(f"Login failed as expected: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await client2.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
