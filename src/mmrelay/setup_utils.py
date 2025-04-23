"""
Setup utilities for MMRelay.

This module provides simple functions for managing the systemd user service
and generating configuration files.
"""

# Import version from package
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_executable_path():
    """Get the full path to the mmrelay executable.

    This function tries to find the mmrelay executable in the PATH,
    which works for both pipx and pip installations.
    """
    mmrelay_path = shutil.which("mmrelay")
    if mmrelay_path:
        print(f"Found mmrelay executable at: {mmrelay_path}")
        return mmrelay_path
    else:
        print("Warning: Could not find mmrelay executable in PATH. Using current Python interpreter.")
        return sys.executable


def get_user_service_path():
    """Get the path to the user service file."""
    service_dir = Path.home() / ".config" / "systemd" / "user"
    return service_dir / "mmrelay.service"


def service_exists():
    """Check if the service file exists."""
    return get_user_service_path().exists()


def print_service_commands():
    """Print the commands for controlling the systemd user service."""
    print("\nUse these commands to control the mmrelay service:")
    print("  systemctl --user start mmrelay.service    # Start the service")
    print("  systemctl --user stop mmrelay.service     # Stop the service")
    print("  systemctl --user restart mmrelay.service  # Restart the service")
    print("  systemctl --user status mmrelay.service   # Check service status")


def wait_for_service_start():
    """Wait for the service to start with a loading animation."""
    import sys
    import time

    print("\nStarting mmrelay service", end="")
    sys.stdout.flush()

    # Animation characters
    chars = ["-", "\\", "|", "/"]

    # Wait for 10 seconds with animation
    for i in range(40):  # 40 * 0.25s = 10s
        time.sleep(0.25)
        print(f"\rStarting mmrelay service {chars[i % len(chars)]}", end="")
        sys.stdout.flush()

    print("\rStarting mmrelay service... done!")
    sys.stdout.flush()


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

    # Try to find the service template file
    # First, check in the package directory
    package_dir = os.path.dirname(__file__)
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(package_dir)), "tools", "mmrelay.service"
    )

    # If not found, try the repository root
    if not os.path.exists(template_path):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        template_path = os.path.join(repo_root, "tools", "mmrelay.service")

    # If still not found, try the current directory
    if not os.path.exists(template_path):
        template_path = os.path.join(os.getcwd(), "tools", "mmrelay.service")

    if not os.path.exists(template_path):
        print(f"Error: Could not find service template at {template_path}")
        return False

    # Read the template
    with open(template_path, "r") as f:
        service_template = f.read()

    # Replace placeholders with actual values
    service_content = (
        service_template.replace(
            "WorkingDirectory=%h/meshtastic-matrix-relay",
            "# WorkingDirectory is not needed for installed package",
        )
        .replace(
            "%h/meshtastic-matrix-relay/.pyenv/bin/python %h/meshtastic-matrix-relay/main.py",
            executable_path,
        )
        .replace(
            "--config %h/.mmrelay/config/config.yaml",
            "--config %h/.mmrelay/config.yaml",
        )
    )

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

    if existing_service:
        print(f"A service file already exists at {get_user_service_path()}")
        if (
            not input("Do you want to reinstall/update the service? (y/n): ")
            .lower()
            .startswith("y")
        ):
            print("Service installation cancelled.")
            print_service_commands()
            return True

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

    # Check if config is valid before starting the service
    from mmrelay.cli import check_config

    if not check_config():
        print(
            "\nWarning: Configuration is not valid. Service is installed but not started."
        )
        print("Please fix your configuration and then start the service manually.")
        print_service_commands()
        return True

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
        except subprocess.CalledProcessError as e:
            print(f"Error enabling service: {e}")
        except OSError as e:
            print(f"Error: {e}")

    if input("Do you want to start the service now? (y/n): ").lower().startswith("y"):
        if start_service():
            # Wait for the service to start
            wait_for_service_start()

            # Show service status
            show_service_status()
            print("Service started successfully")
        else:
            print("\nWarning: Failed to start the service. Please check the logs.")

    print_service_commands()

    return True


def start_service():
    """Start the systemd user service.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        subprocess.run(
            ["/usr/bin/systemctl", "--user", "start", "mmrelay.service"], check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error starting service: {e}")
        return False
    except OSError as e:
        print(f"Error: {e}")
        return False


def show_service_status():
    """Show the status of the systemd user service.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "--user", "status", "mmrelay.service"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("\nService Status:")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Could not get service status: {e}")
        return False
    except OSError as e:
        print(f"Error: {e}")
        return False
