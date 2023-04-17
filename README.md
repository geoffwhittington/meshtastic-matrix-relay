# Meshtastic <=> Matrix Relay

Simple relay between Meshtastic and Matrix.org

## Installation

Clone the repo

```
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
```

### Setup

In the directory create a Python virtualenv:

```
python3 -m venv .pyenv
```

Activate the virtualenv and install dependencies

```
source .pyenv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `config.yaml` in the directory with the appropriate values. A sample is provided below:

```
matrix:
  homeserver: "https://example.matrix.org"
  access_token: "reaalllllyloooooongsecretttttcodeeeeeeforrrrbot"
  bot_user_id: "@botuser:example.matrix.org"
  room_id: "!someroomid:example.matrix.org"

meshtastic:
  host: "meshtastic.local"
  broadcast_enabled: false

logging:
  level: "debug"
```

## Run

After activating the virtualenv:

```
source .pyenv/bin/activate
```

Run the following on the command-line:

```
python main.py
```

For example,

```
$ python main.py
INFO:meshtastic.matrix.relay:Starting Meshtastic <==> Matrix Relay...
INFO:meshtastic.matrix.relay:Connecting to radio at meshtastic.local ...
INFO:meshtastic.matrix.relay:Connected to radio at meshtastic.local.
INFO:meshtastic.matrix.relay:Listening for inbound radio messages ...
INFO:meshtastic.matrix.relay:Listening for inbound matrix messages ...
```
