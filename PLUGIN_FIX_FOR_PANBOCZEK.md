# Plugin Loading Fix for PanBoczek

## Two Solutions (Choose One)

### Option 1: Fix as Custom Plugin (Recommended)

Your plugin isn't loading because custom plugins need directory structure.

**Current (Broken):**

```text
~/.mmrelay/plugins/custom/tx_to_mesh_plugin.py  (single file)
```

**Required (Working):**

```text
~/.mmrelay/plugins/custom/tx_to_mesh/           (directory)
└── tx_to_mesh_plugin.py                       (file inside)
```

**Fix Commands:**

```bash
# Create directory
mkdir -p ~/.mmrelay/plugins/custom/tx_to_mesh

# Move your plugin file
mv ~/.mmrelay/plugins/custom/tx_to_mesh_plugin.py ~/.mmrelay/plugins/custom/tx_to_mesh/

# Restart MMRelay
```

**Config (already correct):**

```yaml
custom-plugins:
  tx_to_mesh:  # Must match directory name
    active: true
```

### Option 2: Use as Community Plugin

If you prefer the repository approach:

1. **Create repository** on GitHub with your plugin file
2. **Use community plugin config:**

```yaml
community-plugins:
  tx_to_mesh:
    active: true
    repository: https://github.com/YourUsername/tx-to-mesh-plugin.git
    branch: main
```

3. **Remove custom plugin config** and restart MMRelay

## Expected Result

After either fix: `Loaded: ping, nodes, tx_to_mesh`

## What We Need to Fix (Internal Notes)

### 1. Plugin Development Guide (Wiki)

Add clear section explaining:

- **Community plugins**: Use template, create repository, system auto-clones
- **Custom plugins**: Manual directory structure required

### 2. mmr-plugin-template README

Add note that template is for community plugins. For custom plugins, explain directory requirement.

### 3. Plugin Loader Error Messages

Add helpful warnings when directories not found:

```python
logger.warning(
    f"Custom plugin '{plugin_name}' not found. "
    f"Expected directory: ~/.mmrelay/plugins/custom/{plugin_name}/"
)
```

## Root Cause

**Two issues found:**

1. **Documentation confusion**: The mmr-plugin-template is designed for **community plugins** (repositories), but PanBoczek used it for a **custom plugin** (manual installation). Both approaches work, but have different directory requirements that aren't clearly documented.

2. **Docker permission bug**: Plugin loader was trying to create directories in `/usr/local/lib/python3.11/site-packages/mmrelay/plugins/` which fails due to permissions in Docker containers. This affects ALL plugin loading in Docker environments.

**Fixed Docker bug** - Plugin loader now handles permission errors gracefully and skips directories it can't create.

## Testing Results

- ✅ Custom plugin loading works with directory structure
- ✅ Community plugin loading works correctly
- ✅ Template code is correct for community plugins
- ✅ No changes between 1.1.3 and 1.1.4 broke plugin loading
- ❌ Documentation doesn't distinguish installation methods clearly
