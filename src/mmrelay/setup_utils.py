"""
Setup utilities for MMRelay.

This module provides simple functions for managing the systemd user service
and generating configuration files.
"""

import importlib.resources

# Import version from package
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mmrelay.constants.database import PROGRESS_COMPLETE, PROGRESS_TOTAL_STEPS
from mmrelay.tools import get_service_template_path


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
        print(
            "Warning: Could not find mmrelay executable in PATH. Using current Python interpreter."
        )
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
    print("  systemctl --user start mmrelay.service    # Start the service")
    print("  systemctl --user stop mmrelay.service     # Stop the service")
    print("  systemctl --user restart mmrelay.service  # Restart the service")
    print("  systemctl --user status mmrelay.service   # Check service status")


def wait_for_service_start():
    """
    Displays a progress spinner while waiting up to 10 seconds for the mmrelay service to become active.

    The function checks the service status after 5 seconds and completes early if the service is detected as active.
    """
    import time

    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    # Create a Rich progress display with spinner and elapsed time
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]Starting mmrelay service..."),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        # Add a task that will run for approximately 10 seconds
        task = progress.add_task("Starting", total=PROGRESS_TOTAL_STEPS)

        # Update progress over 10 seconds
        for i in range(10):
            time.sleep(1)
            progress.update(task, completed=10 * (i + 1))

            # Check if service is active after 5 seconds to potentially finish early
            if i >= 5 and is_service_active():
                progress.update(task, completed=PROGRESS_COMPLETE)
                break


def read_service_file():
    """Read the content of the service file if it exists."""
    service_path = get_user_service_path()
    if service_path.exists():
        return service_path.read_text()
    return None


def get_template_service_path():
    """Find the path to the template service file.

    Returns:
        str: The path to the template service file, or None if not found.
    """
    # Try to find the service template file
    package_dir = os.path.dirname(__file__)

    # Try to find the service template file in various locations
    template_paths = [
        # Check in the package directory (where it should be after installation)
        os.path.join(package_dir, "mmrelay.service"),
        # Check in a tools subdirectory of the package
        os.path.join(package_dir, "tools", "mmrelay.service"),
        # Check in the data files location (where it should be after installation)
        os.path.join(sys.prefix, "share", "mmrelay", "mmrelay.service"),
        os.path.join(sys.prefix, "share", "mmrelay", "tools", "mmrelay.service"),
        # Check in the user site-packages location
        os.path.join(
            os.path.expanduser("~"), ".local", "share", "mmrelay", "mmrelay.service"
        ),
        os.path.join(
            os.path.expanduser("~"),
            ".local",
            "share",
            "mmrelay",
            "tools",
            "mmrelay.service",
        ),
        # Check one level up from the package directory
        os.path.join(os.path.dirname(package_dir), "tools", "mmrelay.service"),
        # Check two levels up from the package directory (for development)
        os.path.join(
            os.path.dirname(os.path.dirname(package_dir)), "tools", "mmrelay.service"
        ),
        # Check in the repository root (for development)
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "tools",
            "mmrelay.service",
        ),
        # Check in the current directory (fallback)
        os.path.join(os.getcwd(), "tools", "mmrelay.service"),
    ]

    # Try each path until we find one that exists
    for path in template_paths:
        if os.path.exists(path):
            return path

    # If we get here, we couldn't find the template
    # Debug output to help diagnose issues
    print("Debug: Could not find mmrelay.service in any of these locations:")
    for path in template_paths:
        print(f"  - {path}")

    # If we get here, we couldn't find the template
    return None


def get_template_service_content():
    """Get the content of the template service file.

    Returns:
        str: The content of the template service file, or a default template if not found.
    """
    # Use the helper function to get the service template path
    template_path = get_service_template_path()

    if template_path and os.path.exists(template_path):
        # Read the template from file
        try:
            with open(template_path, "r") as f:
                service_template = f.read()
            return service_template
        except Exception as e:
            print(f"Error reading service template file: {e}")

    # If the helper function failed, try using importlib.resources directly
    try:
        service_template = (
            importlib.resources.files("mmrelay.tools")
            .joinpath("mmrelay.service")
            .read_text()
        )
        return service_template
    except (FileNotFoundError, ImportError, OSError) as e:
        print(f"Error accessing mmrelay.service via importlib.resources: {e}")

        # Fall back to the file path method
        template_path = get_template_service_path()
        if template_path:
            # Read the template from file
            try:
                with open(template_path, "r") as f:
                    service_template = f.read()
                return service_template
            except Exception as e:
                print(f"Error reading service template file: {e}")

    # If we couldn't find or read the template file, use a default template
    print("Using default service template")
    return """[Unit]
Description=A Meshtastic <=> Matrix Relay
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# The mmrelay binary can be installed via pipx or pip
ExecStart=%h/.local/bin/mmrelay --config %h/.mmrelay/config.yaml --logfile %h/.mmrelay/logs/mmrelay.log
WorkingDirectory=%h/.mmrelay
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1
# Ensure both pipx and pip environments are properly loaded
Environment=PATH=%h/.local/bin:%h/.local/pipx/venvs/mmrelay/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
"""


def is_service_enabled():
    """Check if the service is enabled.

    Returns:
        bool: True if the service is enabled, False otherwise.
    """
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "--user", "is-enabled", "mmrelay.service"],
            check=False,  # Don't raise an exception if the service is not enabled
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "enabled"
    except Exception:
        return False


def is_service_active():
    """Check if the service is active (running).

    Returns:
        bool: True if the service is active, False otherwise.
    """
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "--user", "is-active", "mmrelay.service"],
            check=False,  # Don't raise an exception if the service is not active
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "active"
    except Exception:
        return False


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

    # Get the template service content
    service_template = get_template_service_content()
    if not service_template:
        print("Error: Could not find service template file")
        return False

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


def service_needs_update():
    """Check if the service file needs to be updated.

    Returns:
        tuple: (needs_update, reason) where needs_update is a boolean and reason is a string
    """
    # Check if service already exists
    existing_service = read_service_file()
    if not existing_service:
        return True, "No existing service file found"

    # Get the template service path
    template_path = get_template_service_path()
    if not template_path:
        return False, "Could not find template service file"

    # Get the executable path
    executable_path = get_executable_path()
    if not executable_path:
        return False, "Could not find mmrelay executable"

    # Check if the ExecStart line in the existing service file contains the correct executable
    if executable_path not in existing_service:
        return (
            True,
            f"Service file does not use the current executable: {executable_path}",
        )

    # Check if the PATH environment includes pipx paths
    if "%h/.local/pipx/venvs/mmrelay/bin" not in existing_service:
        return True, "Service file does not include pipx paths in PATH environment"

    # Check if the service file has been modified recently
    template_mtime = os.path.getmtime(template_path)
    service_path = get_user_service_path()
    if os.path.exists(service_path):
        service_mtime = os.path.getmtime(service_path)
        if template_mtime > service_mtime:
            return True, "Template service file is newer than installed service file"

    return False, "Service file is up to date"


def check_loginctl_available():
    """Check if loginctl is available on the system.

    Returns:
        bool: True if loginctl is available, False otherwise.
    """
    try:
        result = subprocess.run(
            ["which", "loginctl"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_lingering_enabled():
    """
    Determine whether user lingering is enabled for the current user.

    Returns:
        bool: True if user lingering is enabled, False otherwise.
    """
    try:
        username = os.environ.get("USER", os.environ.get("USERNAME"))
        result = subprocess.run(
            ["loginctl", "show-user", username, "--property=Linger"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "Linger=yes" in result.stdout
    except Exception as e:
        print(f"Error checking lingering status: {e}")
        return False


def enable_lingering():
    """Enable user lingering using sudo.

    Returns:
        bool: True if lingering was enabled successfully, False otherwise.
    """
    try:
        username = os.environ.get("USER", os.environ.get("USERNAME"))
        print(f"Enabling lingering for user {username}...")
        result = subprocess.run(
            ["sudo", "loginctl", "enable-linger", username],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Lingering enabled successfully")
            return True
        else:
            print(f"Error enabling lingering: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error enabling lingering: {e}")
        return False


def install_service():
    """
    Install or update the MMRelay systemd user service, guiding the user through creation, updating, enabling, and starting the service as needed.

    Prompts the user for confirmation before updating an existing service file, enabling user lingering, enabling the service to start at boot, and starting or restarting the service. Handles user interruptions gracefully and prints a summary of the service status and management commands upon completion.

    Returns:
        bool: True if the installation or update process completes successfully, False otherwise.
    """
    # Check if service already exists
    existing_service = read_service_file()
    service_path = get_user_service_path()

    # Check if the service needs to be updated
    update_needed, reason = service_needs_update()

    # Check if the service is already installed and if it needs updating
    if existing_service:
        print(f"A service file already exists at {service_path}")

        if update_needed:
            print(f"The service file needs to be updated: {reason}")
            try:
                user_input = input("Do you want to update the service file? (y/n): ")
                if not user_input.lower().startswith("y"):
                    print("Service update cancelled.")
                    print_service_commands()
                    return True
            except (EOFError, KeyboardInterrupt):
                print("\nInput cancelled. Proceeding with default behavior.")
                print("Service update cancelled.")
                print_service_commands()
                return True
        else:
            print(f"No update needed for the service file: {reason}")
    else:
        print(f"No service file found at {service_path}")
        print("A new service file will be created.")

    # Create or update service file if needed
    if not existing_service or update_needed:
        if not create_service_file():
            return False

        # Reload daemon (continue even if this fails)
        if not reload_daemon():
            print(
                "Warning: Failed to reload systemd daemon. You may need to run 'systemctl --user daemon-reload' manually."
            )

        if existing_service:
            print("Service file updated successfully")
        else:
            print("Service file created successfully")

    # We don't need to validate the config here as it will be validated when the service starts

    # Check if loginctl is available
    loginctl_available = check_loginctl_available()
    if loginctl_available:
        # Check if user lingering is enabled
        lingering_enabled = check_lingering_enabled()
        if not lingering_enabled:
            print(
                "\nUser lingering is not enabled. This is required for the service to start automatically at boot."
            )
            print(
                "Lingering allows user services to run even when you're not logged in."
            )
            try:
                user_input = input(
                    "Do you want to enable lingering for your user? (requires sudo) (y/n): "
                )
                should_enable_lingering = user_input.lower().startswith("y")
            except (EOFError, KeyboardInterrupt):
                print("\nInput cancelled. Skipping lingering setup.")
                should_enable_lingering = False

            if should_enable_lingering:
                enable_lingering()

    # Check if the service is already enabled
    service_enabled = is_service_enabled()
    if service_enabled:
        print("The service is already enabled to start at boot.")
    else:
        print("The service is not currently enabled to start at boot.")
        try:
            user_input = input(
                "Do you want to enable the service to start at boot? (y/n): "
            )
            enable_service = user_input.lower().startswith("y")
        except (EOFError, KeyboardInterrupt):
            print("\nInput cancelled. Skipping service enable.")
            enable_service = False

        if enable_service:
            try:
                subprocess.run(
                    ["/usr/bin/systemctl", "--user", "enable", "mmrelay.service"],
                    check=True,
                )
                print("Service enabled successfully")
                service_enabled = True
            except subprocess.CalledProcessError as e:
                print(f"Error enabling service: {e}")
            except OSError as e:
                print(f"Error: {e}")

    # Check if the service is already running
    service_active = is_service_active()
    if service_active:
        print("The service is already running.")
        try:
            user_input = input("Do you want to restart the service? (y/n): ")
            restart_service = user_input.lower().startswith("y")
        except (EOFError, KeyboardInterrupt):
            print("\nInput cancelled. Skipping service restart.")
            restart_service = False

        if restart_service:
            try:
                subprocess.run(
                    ["/usr/bin/systemctl", "--user", "restart", "mmrelay.service"],
                    check=True,
                )
                print("Service restarted successfully")
                # Wait for the service to restart
                wait_for_service_start()
                # Show service status
                show_service_status()
            except subprocess.CalledProcessError as e:
                print(f"Error restarting service: {e}")
            except OSError as e:
                print(f"Error: {e}")
    else:
        print("The service is not currently running.")
        try:
            user_input = input("Do you want to start the service now? (y/n): ")
            start_now = user_input.lower().startswith("y")
        except (EOFError, KeyboardInterrupt):
            print("\nInput cancelled. Skipping service start.")
            start_now = False

        if start_now:
            if start_service():
                # Wait for the service to start
                wait_for_service_start()
                # Show service status
                show_service_status()
                print("Service started successfully")
            else:
                print("\nWarning: Failed to start the service. Please check the logs.")

    # Print a summary of the service status
    print("\nService Status Summary:")
    print(f"  Service File: {service_path}")
    print(f"  Enabled at Boot: {'Yes' if service_enabled else 'No'}")
    if loginctl_available:
        print(f"  User Lingering: {'Yes' if check_lingering_enabled() else 'No'}")
    print(f"  Currently Running: {'Yes' if is_service_active() else 'No'}")
    print("\nService Management Commands:")
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
