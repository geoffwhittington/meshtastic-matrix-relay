"""
Setup utilities for MMRelay.

This module provides simple functions for managing the systemd user service.
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Import version from package

# Service file template
USER_SERVICE_TEMPLATE = """[Unit]
Description=Meshtastic <==> Matrix Relay
After=default.target

[Service]
Type=idle
ExecStart={executable_path} --config %h/.mmrelay/config.yaml --logfile %h/.mmrelay/logs/mmrelay.log
Restart=on-failure

[Install]
WantedBy=default.target
"""


def get_executable_path():
    """Get the full path to the mmrelay executable."""
    return shutil.which("mmrelay") or sys.executable


def get_user_service_path():
    """Get the path to the user service file."""
    service_dir = Path.home() / ".config" / "systemd" / "user"
    return service_dir / "mmrelay.service"


def service_exists():
    """Check if the service file exists."""
    return get_user_service_path().exists()


def read_service_file():
    """Read the content of the service file if it exists."""
    service_path = get_user_service_path()
    if service_path.exists():
        return service_path.read_text()
    return None


def create_service_file():
    """Create the systemd user service file."""
    executable_path = get_executable_path()
    if not executable_path:
        print("Error: Could not find mmrelay executable in PATH")
        return False

    # Create service directory if it doesn't exist
    service_dir = get_user_service_path().parent
    service_dir.mkdir(parents=True, exist_ok=True)

    # Create logs directory if it doesn't exist
    logs_dir = Path.home() / ".mmrelay" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate service file content
    service_content = USER_SERVICE_TEMPLATE.format(executable_path=executable_path)

    # Write service file
    try:
        get_user_service_path().write_text(service_content)
        print(f"Service file created at {get_user_service_path()}")
        return True
    except (IOError, OSError) as e:
        print(f"Error creating service file: {e}")
        return False


def reload_daemon():
    """Reload the systemd user daemon."""
    try:
        # Using absolute path for security
        subprocess.run(["/usr/bin/systemctl", "--user", "daemon-reload"], check=True)
        print("Systemd user daemon reloaded")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error reloading systemd daemon: {e}")
        return False
    except OSError as e:
        print(f"Error: {e}")
        return False


def install_service():
    """Install or update the MMRelay user service."""
    # Check if service already exists
    existing_service = read_service_file()

    # Create or update service file
    if not create_service_file():
        return False

    # Reload daemon
    if not reload_daemon():
        return False

    if existing_service:
        print("Service updated successfully")
    else:
        print("Service installed successfully")

    # Ask if user wants to enable and start the service
    if (
        input("Do you want to enable the service to start at boot? (y/n): ")
        .lower()
        .startswith("y")
    ):
        try:
            subprocess.run(
                ["/usr/bin/systemctl", "--user", "enable", "mmrelay.service"],
                check=True,
            )
            print("Service enabled successfully")
        except subprocess.SubprocessError as e:
            print(f"Error enabling service: {e}")

    if input("Do you want to start the service now? (y/n): ").lower().startswith("y"):
        try:
            subprocess.run(
                ["/usr/bin/systemctl", "--user", "start", "mmrelay.service"], check=True
            )
            print("Service started successfully")

            # Show status
            try:
                result = subprocess.run(
                    ["/usr/bin/systemctl", "--user", "status", "mmrelay.service"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print("\nService Status:")
                print(result.stdout)
            except subprocess.SubprocessError:
                print("Could not get service status")
        except subprocess.SubprocessError as e:
            print(f"Error starting service: {e}")

    print("\nYou can control the service with these commands:")
    print("  systemctl --user start mmrelay.service")
    print("  systemctl --user stop mmrelay.service")
    print("  systemctl --user restart mmrelay.service")
    print("  systemctl --user status mmrelay.service")

    return True
