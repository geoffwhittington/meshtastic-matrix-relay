# Meshtastic <=> Matrix Relay

A powerful and easy-to-use relay between Meshtastic devices and Matrix chat rooms, allowing seamless communication across platforms. This opens the door for bridging Meshtastic devices to [many other networks](https://matrix.org/bridges/).

## Features

- Bidirectional message relay between Meshtastic devices and Matrix chat rooms, capable of supporting multiple meshnets
-  Supports both serial and network connections for Meshtastic devices
- Custom keys are embedded in Matrix messages with information (Meshtastic longname + meshnet name) which are used when relaying messages between two or more meshnets. 
- Truncates long messages to fit within Meshtastic's payload size
- SQLite database to store Meshtastic longnames for improved functionality
- Customizable logging level for easy debugging
- Configurable through a simple YAML file

## Custom Keys in Matrix Messages

This relay utilizes custom keys in Matrix messages to store metadata about Meshtastic users. When a message is received from a remote meshnet, the relay includes the sender's longname and the meshnet name as custom keys in the Matrix message. This metadata helps identify the source of the message and provides context for users in the Matrix chat room.

Example message format with custom keys:

```
{
"msgtype": "m.text",
"body": "[Alice/RemoteMesh]: Hello from the remote meshnet!",
"meshtastic_longname": "Alice",
"meshtastic_meshnet": "RemoteMesh"
}
```

## Installation

Clone the repository:

```
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
```

### Setup

Create a Python virtual environment in the project directory:

```
python3 -m venv .pyenv
```

Activate the virtual environment and install dependencies:

```
source .pyenv/bin/activate
pip install -r requirements.txt
```


### Configuration

Create a `config.yaml` in the project directory with the appropriate values. A sample configuration is provided below:

```yaml
matrix:
  homeserver: "https://example.matrix.org"
  access_token: "reaalllllyloooooongsecretttttcodeeeeeeforrrrbot"
  bot_user_id: "@botuser:example.matrix.org"
  room_id: "!someroomid:example.matrix.org"

meshtastic:
  connection_type: serial  # Choose either "network" or "serial"
  serial_port: /dev/ttyUSB0  # Only used when connection is "serial"
  host: "meshtastic.local"  # Only used when connection is "network"
  channel: 0    # Channel ID of the Meshtastic Channel you want to relay
  meshnet_name: "Your Meshnet Name"  # This is displayed in full on Matrix, but is truncated when sent to a remote Meshnet
  display_meshnet_name: true

logging:
  level: "debug"
```

## Usage
Activate the virtual environment:
```
source .pyenv/bin/activate
```
Run the `main.py` script:
```
python main.py
```
Example output:
```
$ python main.py
INFO:meshtastic.matrix.relay:Starting Meshtastic <==> Matrix Relay...
INFO:meshtastic.matrix.relay:Connecting to radio at meshtastic.local ...
INFO:meshtastic.matrix.relay:Connected to radio at meshtastic.local.
INFO:meshtastic.matrix.relay:Listening for inbound radio messages ...
INFO:meshtastic.matrix.relay:Listening for inbound matrix messages ...
INFO:meshtastic.matrix.relay:Sending radio message from Alice to radio broadcast
INFO:meshtastic.matrix.relay:Processing inbound radio message from !613501e4
INFO:meshtastic.matrix.relay:Processing matrix message from @bob:matrix.org: Hi Alice!
INFO:meshtastic.matrix.relay:Sending radio message from Alice to radio broadcast
INFO:meshtastic.matrix.relay:Processing inbound radio message from !613501e4
```
