# Matrix End-to-End Encryption (E2EE) Guide

**MMRelay v1.2+** includes full support for **Matrix End-to-End Encryption**, enabling secure communication in encrypted Matrix rooms. This guide covers everything you need to set up and use E2EE features.

## What is E2EE?

End-to-End Encryption ensures that only you and the intended recipients can read your messages. When MMRelay connects to encrypted Matrix rooms, it will:

- **Automatically encrypt** outgoing messages to encrypted rooms
- **Automatically decrypt** incoming messages from encrypted rooms, requesting keys as needed
- **Maintain device identity** across sessions for consistent encryption
- **Handle mixed environments** with both encrypted and unencrypted rooms seamlessly

## Quick Start

### 1. Install E2EE Support

```bash
# Install MMRelay with E2EE support
pip install mmrelay[e2e]

# Or if using pipx
pipx install mmrelay[e2e]
```

### 2. Enable E2EE in Configuration

Add E2EE configuration to your `~/.mmrelay/config.yaml`:

```yaml
matrix:
  homeserver: https://your-matrix-server.org

  # E2EE Configuration
  e2ee:
    enabled: true
```

### 3. Set Up Authentication

Use the built-in authentication command to create your bot's E2EE-enabled credentials:

```bash
mmrelay --bot_login
```

This interactive command will:
- Prompt for your Matrix homeserver, username, and password
- Create secure credentials with E2EE support
- Save authentication details to `~/.mmrelay/credentials.json`
- Set up encryption keys for secure communication

### 4. Start MMRelay

```bash
mmrelay
```

That's it! MMRelay will automatically encrypt messages for encrypted rooms and decrypt incoming encrypted messages. The first time it sees an encrypted message from a new device, it may log a "Failed to decrypt" error, but it will automatically request the necessary keys and decrypt the message on the next sync.

## Requirements

- **Python 3.9 or higher**
- **Linux or macOS** (E2EE is not supported on Windows due to library limitations)
- **MMRelay v1.2+** with E2EE support: `pip install mmrelay[e2e]`
- **Matrix homeserver** that supports E2EE (most modern servers do)
- **Dedicated bot account** recommended (don't use your personal Matrix account)

### Windows Limitation

**E2EE is not available on Windows** due to technical limitations with the required cryptographic libraries. The `python-olm` library requires native C libraries that are difficult to compile and install on Windows systems.

**Windows users can still use MMRelay** for regular (unencrypted) Matrix communication by configuring Matrix credentials directly in `config.yaml` instead of using the `--bot_login` command.

### Step 2: Create E2EE Credentials

Use the authentication command to create E2EE credentials:

```bash
# Create E2EE credentials (interactive)
mmrelay --bot_login
```

**What the `--bot_login` command does:**
1. Prompts for your Matrix homeserver, username, and password
2. Creates a new Matrix session with E2EE support
3. Generates a unique device ID for MMRelay
4. Saves credentials to `~/.mmrelay/credentials.json`
5. Sets up encryption key storage in `~/.mmrelay/store/`

**Interactive prompts:**
```
Matrix Bot Login for E2EE
=========================
Matrix homeserver (e.g., https://matrix.org): https://your-server.org
Matrix username (e.g., @user:matrix.org): @yourbot:your-server.org
Matrix password: [hidden input]
```

### Step 3: Start MMRelay

Once configured, start MMRelay normally:

```bash
mmrelay
```

MMRelay will automatically:
- Load E2EE credentials from `credentials.json`
- Initialize encryption keys and device trust
- Connect to Matrix with full E2EE support

## The `--bot_login` Command

The `--bot_login` command is the recommended way to set up Matrix authentication for MMRelay v1.2+. It provides secure credential management with full E2EE support.

### What It Does

```bash
mmrelay --bot_login
```

**The authentication process:**
1. **Interactive Setup**: Prompts for Matrix homeserver, username, and password
2. **Secure Login**: Creates a new Matrix session with encryption enabled
3. **Device Registration**: Generates a unique, persistent device ID for MMRelay
4. **Credential Storage**: Saves authentication details to `~/.mmrelay/credentials.json`
5. **Key Setup**: Initializes encryption key storage in `~/.mmrelay/store/`

### Example Session

```
$ mmrelay --bot_login
Matrix Bot Login for E2EE
=========================
Matrix homeserver (e.g., https://matrix.org): https://matrix.example.org
Matrix username (e.g., @user:matrix.org): @mmrelay-bot:matrix.example.org
Matrix password: [password hidden]

✅ Login successful!
✅ Device ID: MMRELAY_ABC123DEF
✅ Credentials saved to ~/.mmrelay/credentials.json
✅ E2EE store initialized at ~/.mmrelay/store/

You can now start MMRelay with: mmrelay
```

### Files Created

**`~/.mmrelay/credentials.json`** - Contains your Matrix session:
```json
{
  "homeserver": "https://matrix.example.org",
  "user_id": "@mmrelay-bot:matrix.example.org",
  "access_token": "your_access_token_here",
  "device_id": "MMRELAY_ABC123DEF"
}
```

**`~/.mmrelay/store/`** - Directory containing encryption keys and device information (multiple database files).

### Security Benefits

- **Secure Storage**: Credentials are stored locally, not in plain text config files
- **Device Persistence**: Same device ID across restarts maintains encryption history
- **E2EE Ready**: Automatically sets up everything needed for encrypted communication
- **Isolated Sessions**: Creates dedicated bot sessions separate from personal accounts

## How It Works

### Automatic Encryption Detection

MMRelay automatically detects room encryption status:

- **Encrypted rooms**: Messages are automatically encrypted before sending
- **Unencrypted rooms**: Messages are sent as normal plaintext
- **Mixed environments**: Each room is handled according to its encryption status

### Device Management

MMRelay manages encryption devices automatically:

- **Consistent Device ID**: Maintains the same device identity across restarts
- **Key Storage**: Encryption keys are stored securely in `~/.mmrelay/store/`
- **Automatic Key Sharing**: When the bot sees an encrypted message it can't read, it automatically requests the necessary keys from other clients in the room.
- **Device Trust**: Uses `ignore_unverified_devices=True` for reliable operation
- **Key Upload**: Automatically uploads encryption keys when needed

### Message Flow

1. **Outgoing Messages** (Meshtastic → Matrix):
   - MMRelay receives message from Meshtastic device
   - Checks if target Matrix room is encrypted
   - If encrypted: Encrypts message using room's encryption keys
   - Sends encrypted message to Matrix room

2. **Incoming Messages** (Matrix → Meshtastic):
   - MMRelay receives an encrypted message from a Matrix room.
   - If it cannot be decrypted, the bot automatically requests the key.
   - On a subsequent sync, the bot receives the key and decrypts the message.
   - Forwards decrypted message to Meshtastic device.

## File Locations

### Configuration Files

- **Main Config**: `~/.mmrelay/config.yaml`
- **E2EE Credentials**: `~/.mmrelay/credentials.json`
- **Encryption Store**: `~/.mmrelay/store/` (directory)

### Credentials File Format

The `credentials.json` file contains:

```json
{
  "homeserver": "https://your-matrix-server.org",
  "user_id": "@your-bot:your-matrix-server.org", 
  "access_token": "your_access_token_here",
  "device_id": "MMRELAY_DEVICE_ID"
}
```

**Important**: Keep this file secure as it contains your Matrix access credentials.

## Troubleshooting

### Common Issues

#### "E2EE features not available on Windows"

**Problem**: E2EE features don't work on Windows even with `mmrelay --bot_login`.

**Explanation**: E2EE requires the `python-olm` library, which depends on native C libraries that are difficult to compile on Windows.

**Solutions**:
- **Use Linux or macOS** for full E2EE support
- **On Windows**: `mmrelay --bot_login` still works for regular Matrix communication
- **Alternative**: Configure credentials manually in `config.yaml`:
  ```yaml
  matrix:
    homeserver: https://your-matrix-server.org
    access_token: your_access_token
    bot_user_id: @yourbot:your-matrix-server.org
  ```

**Note**: Credentials created with `mmrelay --bot_login` on Windows will work with E2EE if you later use them on Linux/macOS.

#### "No E2EE dependencies found"

**Solution**: Install E2EE dependencies (Linux/macOS only):
```bash
pip install mmrelay[e2e]
```

#### "Failed to decrypt event" error in logs

**Problem**: You see `ERROR Matrix: Failed to decrypt event...` in your logs.

**Explanation**: This is usually normal, temporary behavior. It happens when another user sends a message in an encrypted room and the relay doesn't have the decryption key for it yet.

**Solution**:
- **Wait**: The relay will automatically request the key in the background. The message should be successfully decrypted within the next minute during the next sync from the server.
- **If the error persists for a long time**: This might indicate a de-synchronized session. The best way to fix this is to regenerate your credentials and key store.
  ```bash
  # Remove old credentials and store
  rm ~/.mmrelay/credentials.json
  rm -rf ~/.mmrelay/store/

  # Create new credentials
  mmrelay --bot_login
  ```

### Verification and Testing

#### Check E2EE Status

Look for these log messages when MMRelay starts:

```
INFO Matrix: Found credentials at ~/.mmrelay/credentials.json
INFO Matrix: Using device ID: YOUR_DEVICE_ID
INFO Matrix: Setting up End-to-End Encryption...
INFO Matrix: Encryption keys uploaded successfully
INFO Matrix: Performing initial sync to initialize rooms...
INFO Matrix: Initial sync completed. Found X rooms.
```

#### Verify Message Encryption

In your Matrix client (Element, etc.):
- **Encrypted messages**: Show with a lock icon or green shield.
- **Unencrypted messages**: Show with a red shield and "Not encrypted" warning.

If messages from MMRelay show as unencrypted in encrypted rooms, check your MMRelay version and configuration.

## Security Considerations

### Device Verification

MMRelay uses `ignore_unverified_devices=True` for automated bot operation:
- Interactive device verification is not practical for automated bots
- This setting allows reliable operation while maintaining encryption

### Key Storage

- Encryption keys are stored in `~/.mmrelay/store/`
- This directory should be backed up to preserve encryption history
- Protect this directory with appropriate file permissions
- Consider encrypting the filesystem where this directory is stored

### Access Control

- The `credentials.json` file contains sensitive authentication data
- Limit access to this file to the user running MMRelay
- Consider using environment variables for additional security

## Backward Compatibility

E2EE support is fully backward compatible:

- **Existing setups**: Continue to work without changes
- **Mixed environments**: Can handle both encrypted and unencrypted rooms
- **Optional feature**: E2EE can be disabled by setting `e2ee.enabled: false`

## Technical Details

### Implementation

- Uses matrix-nio library with Olm/Megolm encryption protocols
- E2EE store loaded before sync operations for proper initialization
- Automatic key management with `ignore_unverified_devices=True`

### Performance Impact

E2EE adds minimal overhead:
- **Startup time**: Slightly longer due to key synchronization
- **Message latency**: Negligible encryption/decryption time
- **Memory usage**: Small increase for key storage
- **Network usage**: Additional sync traffic for key management

For questions or issues with E2EE support, please check the [GitHub Issues](https://github.com/jeremiah-k/meshtastic-matrix-relay/issues) or create a new issue with the `e2ee` label.
