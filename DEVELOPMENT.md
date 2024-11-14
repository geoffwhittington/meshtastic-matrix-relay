# Development

The relay is compatible with Python 3.9 and newer on Linux, macOS, and Windows. We encourage contributions to fix bugs or add enhancements.

## Installation

Clone the repository:

```bash
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
```

### Setup

Create a Python virtual environment in the project directory:

```bash
python3 -m venv .pyenv
```

Activate the virtual environment and install dependencies:

```bash
source .pyenv/bin/activate
pip install -r requirements.txt
```

### Configuration

To configure the relay, create a `config.yaml` file in the project directory. You can refer to the provided `sample_config.yaml` for an example configuration.

## Usage

Activate the virtual environment:

```bash
source .pyenv/bin/activate
```

Run the `main.py` script:

```bash
python main.py
```

Example output:

```bash
python main.py
INFO:meshtastic.matrix.relay:Starting Meshtastic <==> Matrix Relay...
INFO:meshtastic.matrix.relay:Connecting to radio at meshtastic.local ...
INFO:meshtastic.matrix.relay:Connected to radio at meshtastic.local.
INFO:meshtastic.matrix.relay:Listening for inbound radio messages ...
INFO:meshtastic.matrix.relay:Listening for inbound matrix messages ...
INFO:meshtastic.matrix.relay:Processing matrix message from @bob:matrix.org: Hi Alice!
INFO:meshtastic.matrix.relay:Sending radio message from Bob to radio broadcast
INFO:meshtastic.matrix.relay:Processing inbound radio message from !613501e4 on channel 0
INFO:meshtastic.matrix.relay:Relaying Meshtastic message from Alice to Matrix: [Alice/VeryCoolMeshnet]: Hey Bob!
INFO:meshtastic.matrix.relay:Sent inbound radio message to matrix room: #someroomid:example.matrix.org
```

## Persistence

To run the bridge automatically on startup in Linux, set up a systemd service:

```systemd
[Unit]
Description=A Meshtastic to Matrix bridge
After=default.target

[Service]
Type=idle
WorkingDirectory=%h/meshtastic-matrix-relay
ExecStart=%h/meshtastic-matrix-relay/.pyenv/bin/python %h/meshtastic-matrix-relay/main.py
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start the service:

```bash
systemctl --user enable mmrelay.service
systemctl --user start mmrelay.service
```

### Contributing & Code Quality Checks

We use **Trunk** for automated code quality checks and formatting. Contributors are expected to run these checks before submitting a pull request.

#### Installing Trunk

Follow these steps to set up Trunk:

1. Install Trunk via the official installation script:

   ```bash
   curl -fsSL https://get.trunk.io | bash
   ```

2. Initialize Trunk in your local environment:

   ```bash
   trunk init
   ```

3. To check your code and automatically fix issues, run:

   ```bash
   trunk check --all --fix
   ```

Refer to the [Trunk documentation](https://trunk.io/docs) for more details on using Trunk effectively.
