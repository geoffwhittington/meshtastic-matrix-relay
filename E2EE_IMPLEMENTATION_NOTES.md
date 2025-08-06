# E2EE Implementation Notes - Branch e2ee-86-1

**⚠️ IMPORTANT: This is the ONLY temporary .md file for this project. It is ephemeral and will NOT be committed to main. All other documentation should use codeblocks.**

## Project Context
- **Goal**: Implement E2EE support for Matrix messages in meshtastic-matrix-relay
- **Duration**: Attempted for 2.5 years since project inception
- **Challenge**: matrix-nio's encryption implementation is buggy/lacking
- **Branch**: e2ee-86-1 (fresh approach)

## Key Constraints & Requirements

### Matrix-nio Limitations
- ❌ Verification does not work (interactive or self-verification)
- ✅ Must use `ignore_unverified_devices = True`
- ✅ Must set proper store path
- ✅ Must upload keys manually
- ✅ Must initiate session ourselves

### MAS (Matrix Authentication Service) Issues
- Matrix.org tokens expire quickly with MAS
- Focus on legacy server setups
- New sessions required (existing tokens don't work for E2EE)

### Compatibility Requirements
- ✅ Support existing setups (no E2EE for them)
- ✅ Send/receive encrypted messages in encrypted rooms
- ✅ Register new callbacks
- ✅ Only use methods from ~/dev/e2ee-examples projects

### Testing & Quality
- ❌ Red shield issue: Hard to distinguish unverified vs unencrypted messages
- ✅ Must write tests once basic functionality works
- ✅ Commit and push often for CI testing
- ✅ Don't break basic functionality

## Resources to Analyze
1. **Existing draft**: `e2ee-implementation` branch
2. **Examples**: `~/dev/e2ee-examples` directory
3. **nio source**: Available in examples directory

## Implementation Strategy
- Learn from previous attempts to avoid trial and error
- Analyze existing draft for design decisions
- Use proven methods from example projects only
- Test incrementally to maintain basic functionality

## Analysis Results - Existing E2EE Implementation

### Key Findings from e2ee-implementation branch:

#### Configuration Structure
- Uses both `encryption` and `e2ee` keys for backward compatibility
- Supports credentials.json for device_id, access_token, user_id, homeserver
- E2EE store path: `~/.mmrelay/store/` (using platformdirs)
- Requires `mmrelay[e2e]` installation with `matrix-nio[e2e]==0.25.2` and `python-olm`

#### Client Initialization Sequence (CRITICAL)
1. **Early lightweight sync** to initialize rooms (critical for message delivery)
2. **Device ID retrieval** via whoami() and credential validation
3. **Store loading** and key upload BEFORE main sync
4. **Main sync** after keys are uploaded
5. **Device verification** - trust all devices with ignore_unverified_devices=True

#### Callback Registration
- `MegolmEvent` for encrypted messages
- `RoomEncryptionEvent` for room encryption detection
- Standard message callbacks still work for unencrypted messages

#### Key Challenges Identified
- Device verification is buggy in matrix-nio
- Red shield issue: Hard to distinguish unverified vs unencrypted messages
- Existing tokens don't work well with E2EE (need new sessions)
- Complex initialization sequence required for proper functionality

## Analysis Results - E2EE Examples

### Key Patterns from ~/dev/e2ee-examples:

#### nio-template Pattern (Clean & Simple)
```python
# Client config
client_config = AsyncClientConfig(
    store_sync_tokens=True,
    encryption_enabled=True,
)

# Client initialization
client = AsyncClient(
    homeserver_url,
    user_id,
    device_id=device_id,
    store_path=store_path,
    config=client_config,
)

# E2EE setup sequence
if user_token:
    client.load_store()
    if client.should_upload_keys:
        await client.keys_upload()
```

#### matrix-commander Pattern (Comprehensive)
- Always calls `keys_upload()` if `client.should_upload_keys`
- Uses `sync(timeout=30000, full_state=True)` for proper room initialization
- Handles both password and token authentication
- Comprehensive error handling for E2EE failures

#### Common Callback Patterns
- `MegolmEvent` for encrypted messages (with decryption failure handling)
- `RoomMessageText` for regular messages
- `InviteMemberEvent` for room invites
- `UnknownEvent` for reactions and other events

## E2EE Architecture Design

### Configuration Strategy
1. **Backward Compatibility**: Support existing `access_token` setups (no E2EE)
2. **New E2EE Setup**: Use `credentials.json` for E2EE-enabled setups
3. **Optional E2EE**: Add `e2ee.enabled` flag in config.yaml

### Configuration Structure
```yaml
matrix:
  homeserver: https://matrix.example.org
  # Legacy token-based setup (no E2EE)
  access_token: "legacy_token"  # Optional
  bot_user_id: "@bot:example.org"  # Optional

  # E2EE configuration
  e2ee:
    enabled: false  # Default: false for backward compatibility
    store_path: ~/.mmrelay/store  # Optional: defaults to platformdirs
```

### credentials.json Structure (E2EE only)
```json
{
  "homeserver": "https://matrix.example.org",
  "user_id": "@bot:example.org",
  "access_token": "new_session_token",
  "device_id": "MMRELAY_DEVICE_123"
}
```

### Client Initialization Flow
1. **Check for credentials.json** (E2EE path)
2. **Fallback to config.yaml** (legacy path)
3. **Initialize client** with appropriate configuration
4. **E2EE setup sequence** (if enabled):
   - Load store
   - Upload keys if needed
   - Sync with full_state=True
   - Register encrypted message callbacks

### Callback Strategy
- **Existing callbacks**: Keep working for unencrypted messages
- **Add MegolmEvent callback**: Handle encrypted messages
- **Unified message handler**: Process both encrypted and unencrypted messages

## Progress Tracking
- [x] Analyze existing e2ee-implementation branch
- [x] Review ~/dev/e2ee-examples projects
- [x] Create task breakdown
- [ ] Implement basic E2EE structure
- [ ] Test encrypted message sending
- [ ] Test encrypted message receiving
- [ ] Write comprehensive tests
- [ ] Validate no regression in basic functionality

## Notes
- **Never celebrate completion until user confirms**
- **Use interactive feedback when finished with major milestones**
- **Focus on systematic approach over quick fixes**
