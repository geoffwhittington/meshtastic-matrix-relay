# E2EE Troubleshooting Guide

This guide helps troubleshoot common E2EE (End-to-End Encryption) issues with MMRelay.

## Common Issues and Solutions

### 1. "Encryption dependencies aren't installed" Error

**Problem**: E2EE dependencies are missing.

**Solution**:
```bash
pip install -r requirements-e2e.txt
# OR
pip install mmrelay[e2e]
```

### 2. "'user_id' is a required property" Error

**Problem**: This confusing error message appears when login fails, but it's actually a matrix-nio library issue with error message formatting.

**What it really means**: The login failed for a different reason (usually invalid credentials).

**Solution**:
1. Check that your Matrix username and password are correct
2. Verify the homeserver URL is correct (e.g., `https://matrix.org`)
3. Make sure the Matrix account exists and is active
4. Check network connectivity to the Matrix server

**Example of correct vs incorrect**:
```bash
# Correct format
mmrelay --auth
Enter Matrix homeserver URL: https://matrix.org
Enter Matrix username (without @): myusername
Enter Matrix password: [your actual password]

# The error "'user_id' is a required property" usually means:
# - Wrong password
# - Wrong username
# - Wrong homeserver URL
# - Network connectivity issues
```

### 3. Login Hangs or Times Out

**Problem**: The `mmrelay --auth` command hangs at "Logging in..."

**Possible causes**:
- Network connectivity issues
- Slow Matrix server response
- Firewall blocking connections
- DNS resolution problems

**Solutions**:
1. Check network connectivity:
   ```bash
   curl -I https://your-matrix-server.com
   ```

2. Try a different Matrix server (e.g., matrix.org) for testing

3. Check firewall settings

4. Increase timeout values (already implemented in the code)

### 4. Regular MMRelay Hangs After "Early sync completed with 0 rooms"

**Problem**: MMRelay starts but hangs after the early sync.

**Possible causes**:
- E2EE configuration issues
- Missing credentials.json
- Network timeouts during E2EE initialization

**Solutions**:
1. Check if E2EE is enabled in config.yaml:
   ```yaml
   e2ee:
     enabled: true
   ```

2. Ensure credentials.json exists:
   ```bash
   ls ~/.mmrelay/credentials.json
   ```

3. If credentials.json is missing, run:
   ```bash
   mmrelay --auth
   ```

4. Check logs for specific error messages

### 5. How to Verify E2EE is Working

**Steps to verify encryption**:

1. **Install E2EE dependencies**:
   ```bash
   pip install mmrelay[e2e]
   ```

2. **Enable E2EE in config**:
   ```yaml
   e2ee:
     enabled: true
   ```

3. **Create credentials**:
   ```bash
   mmrelay --auth
   ```

4. **Test with encrypted room**:
   - Create an encrypted room in Element/Matrix client
   - Invite your MMRelay bot
   - Send messages both ways
   - Verify messages appear correctly

5. **Check logs for E2EE indicators**:
   - Look for "MegolmEvent" in logs (encrypted messages)
   - Check for "Device store" messages
   - Verify "ignore_unverified_devices=True" messages

## Understanding the Error Messages

### Matrix-nio Library Quirks

The matrix-nio library sometimes shows confusing error messages:

- **"'user_id' is a required property"** = Login failed (wrong credentials)
- **"Error validating response"** = Server returned unexpected response format
- **"LoginError: unknown error"** = Generic login failure

These are library-level validation errors, not MMRelay bugs.

### Successful E2EE Setup Indicators

Look for these log messages to confirm E2EE is working:

```
INFO Matrix: Using E2EE store path: /home/user/.mmrelay/store
INFO Matrix: Restored login session for @bot:server.com with device DEVICEID
DEBUG Matrix: Performing sync AFTER key upload
DEBUG Matrix: Trusting our own devices for encryption...
```

## Testing E2EE

Use the verification script:

```bash
python test_e2ee_verification.py
```

This script checks:
- ✅ E2EE dependencies installed
- ✅ credentials.json exists and is valid
- ✅ Matrix connection works
- 📋 Shows verification steps

## Getting Help

If you're still having issues:

1. **Check the logs** for specific error messages
2. **Run the verification script** to identify the problem
3. **Test with matrix.org** first (more reliable than smaller servers)
4. **Verify network connectivity** to your Matrix server
5. **Check Matrix server status** (some servers have downtime)

## Advanced Debugging

Enable debug logging in config.yaml:
```yaml
logging:
  level: DEBUG
```

This will show detailed E2EE initialization steps and help identify where the process is failing.
