# Cleanup Test Docker Images

## Manual Cleanup via GitHub Web Interface

1. **Navigate to packages**: https://github.com/jeremiah-k/meshtastic-matrix-relay/pkgs/container/mmrelay
2. **Click on each test version** (like `1.1.2-dev-9441413`)
3. **Click "Delete package version"** in the settings
4. **Confirm deletion**

## Automated Cleanup via GitHub CLI

```bash
# Install GitHub CLI if not already installed
# brew install gh  # macOS
# sudo apt install gh  # Ubuntu

# Login to GitHub
gh auth login

# List all package versions
gh api /user/packages/container/mmrelay/versions --jq '.[].name'

# Delete specific test versions (replace with actual version names)
gh api -X DELETE /user/packages/container/mmrelay/versions/VERSION_ID

# Example: Delete all dev versions (be careful!)
gh api /user/packages/container/mmrelay/versions --jq '.[] | select(.name | contains("dev")) | .id' | \
  xargs -I {} gh api -X DELETE /user/packages/container/mmrelay/versions/{}
```

## Automated Cleanup via API Script

```bash
#!/bin/bash
# cleanup-dev-images.sh

GITHUB_TOKEN="your_token_here"
OWNER="jeremiah-k"
PACKAGE="mmrelay"

# Get all package versions
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     "https://api.github.com/users/$OWNER/packages/container/$PACKAGE/versions" | \
jq -r '.[] | select(.name | contains("dev")) | .id' | \
while read version_id; do
  echo "Deleting version ID: $version_id"
  curl -X DELETE \
       -H "Authorization: Bearer $GITHUB_TOKEN" \
       -H "Accept: application/vnd.github.v3+json" \
       "https://api.github.com/users/$OWNER/packages/container/$PACKAGE/versions/$version_id"
done
```

## Prevent Future Test Image Accumulation

### Option 1: Add cleanup step to workflow

```yaml
- name: Cleanup old dev images
  if: github.event_name != 'release'
  run: |
    # Keep only the latest 3 dev images
    gh api /user/packages/container/mmrelay/versions --jq '.[3:] | .[] | select(.name | contains("dev")) | .id' | \
      xargs -I {} gh api -X DELETE /user/packages/container/mmrelay/versions/{}
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Option 2: Use GitHub's automatic cleanup policies

1. Go to package settings
2. Enable "Delete package versions"
3. Set retention policy (e.g., keep last 10 versions)
4. Set up rules for dev/test tags

## Current Test Images to Clean

Based on your description, you have:
- `1.1.2-dev-9441413` (test image)
- Any other `-dev-` tagged images

**Recommendation**: Keep only the latest successful build and delete all test/dev versions.