# Docker Automation Setup Guide

**Date**: July 27, 2025  
**Purpose**: Automate Docker image builds when releases are published in the main repository  
**Current Status**: Manual triggers only  

## 🎯 Current Situation Analysis

### Repository Structure
- **Main Repository**: `geoffwhittington/meshtastic-matrix-relay` (releases published here)
- **Docker Build Repository**: `jeremiah-k/meshtastic-matrix-relay` (your fork with secrets)
- **Challenge**: You maintain the project but don't have access to main repo secrets

### Current Automation Status
- ✅ **Docker workflow works**: Successfully builds and pushes images
- ✅ **Manual triggers work**: `workflow_dispatch` allows manual builds
- ⚠️ **Partial automation**: `check-upstream-releases.yml` exists but requires manual trigger
- ❌ **No automatic triggers**: No automation when main repo publishes releases

## 🐳 Docker Registry Options

### Current: Docker Hub (docker.io)
- **Account**: tadchilly
- **Repository**: tadchilly/mmrelay
- **Free Tier Limits**:
  - ✅ **Unlimited public repositories**
  - ✅ **Unlimited pushes** (no specific limits)
  - ✅ **100 pulls/hour** (authenticated users)
  - ⚠️ **10 pulls/hour** (anonymous users - could be limiting)

### Recommended: GitHub Container Registry (GHCR)
- **URL**: `ghcr.io/jeremiah-k/mmrelay`
- **Benefits**:
  - ✅ **Completely free** for public packages
  - ✅ **No pull rate limits** for public images
  - ✅ **Integrated authentication** (uses GitHub tokens)
  - ✅ **Better GitHub Actions integration**
  - ✅ **Automatic cleanup policies** available
  - ✅ **No separate account needed**

### Alternative Options
1. **Quay.io**: Free unlimited public repos, advanced security scanning
2. **GitLab Container Registry**: 10GB free storage
3. **Self-hosted**: Harbor, Docker Registry, Gitea Container Registry

## 🤖 Automation Solutions

### Option 1: Scheduled Monitoring (RECOMMENDED)

**Implementation**: Modify existing `check-upstream-releases.yml` to run automatically

```yaml
name: Auto-Build Docker Images on Upstream Releases

on:
  schedule:
    # Check every 30 minutes
    - cron: '*/30 * * * *'
  workflow_dispatch: # Keep manual trigger

jobs:
  check-and-build:
    runs-on: ubuntu-latest
    if: github.repository == 'jeremiah-k/meshtastic-matrix-relay'
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        
      - name: Check for new releases
        id: check
        run: |
          # Get latest release from main repo
          LATEST_RELEASE=$(curl -s https://api.github.com/repos/geoffwhittington/meshtastic-matrix-relay/releases/latest | jq -r '.tag_name')
          
          if [ "$LATEST_RELEASE" = "null" ]; then
            echo "No releases found"
            exit 0
          fi
          
          # Check if Docker image exists
          DOCKER_TAG=${LATEST_RELEASE#v}
          DOCKER_CHECK=$(curl -s "https://hub.docker.com/v2/repositories/tadchilly/mmrelay/tags/${DOCKER_TAG}" | jq -r '.name // "null"')
          
          if [ "$DOCKER_CHECK" = "null" ]; then
            echo "New release found: $LATEST_RELEASE"
            echo "should_build=true" >> $GITHUB_OUTPUT
            echo "release_tag=$LATEST_RELEASE" >> $GITHUB_OUTPUT
          fi
          
      - name: Trigger Docker build
        if: steps.check.outputs.should_build == 'true'
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          repository: jeremiah-k/meshtastic-matrix-relay
          event-type: release-published
          client-payload: '{"release_tag": "${{ steps.check.outputs.release_tag }}"}'
```

**Benefits**:
- ✅ Fully automated (no manual intervention)
- ✅ Checks every 30 minutes for new releases
- ✅ Only builds if Docker image doesn't exist
- ✅ No changes needed to main repository
- ✅ Uses existing workflow infrastructure

### Option 2: GitHub App/Webhook (Advanced)

**Implementation**: Create GitHub App that listens to release events

**Benefits**:
- ✅ Instant triggering on release
- ✅ Most efficient (no polling)

**Drawbacks**:
- ❌ Complex setup (GitHub App creation, webhook handling)
- ❌ Requires app installation on main repo (permission needed)
- ❌ Maintenance overhead

### Option 3: Repository Dispatch from Main Repo (Ideal but Limited)

**Implementation**: Add workflow to main repo that triggers your build

```yaml
# In geoffwhittington/meshtastic-matrix-relay
name: Trigger Docker Build
on:
  release:
    types: [published]
    
jobs:
  trigger-docker:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Docker build in fork
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.DOCKER_BUILD_TOKEN }}
          repository: jeremiah-k/meshtastic-matrix-relay
          event-type: release-published
          client-payload: '{"release_tag": "${{ github.event.release.tag_name }}"}'
```

**Benefits**:
- ✅ Instant triggering
- ✅ Most reliable

**Drawbacks**:
- ❌ Requires access to main repo
- ❌ Needs secret in main repo
- ❌ Not feasible with current permissions

## 🛠️ Implementation Plan

### Phase 1: Switch to GHCR (Optional but Recommended)

1. **Update Docker workflow** to use GHCR:
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: jeremiah-k/mmrelay
```

2. **Update secrets**:
   - Use `GITHUB_TOKEN` instead of `DOCKER_TOKEN`
   - No username needed (uses GitHub username)

3. **Benefits**:
   - No rate limits for users
   - Better integration
   - No separate account management

### Phase 2: Enable Scheduled Automation

1. **Update `check-upstream-releases.yml`**:
   - Add cron schedule (every 30 minutes)
   - Improve error handling
   - Add notifications (optional)

2. **Test automation**:
   - Verify scheduled runs work
   - Test with mock release
   - Validate Docker image building

### Phase 3: Optimize and Monitor

1. **Add monitoring**:
   - Slack/Discord notifications on build success/failure
   - Build status badges
   - Automated testing of built images

2. **Optimize frequency**:
   - Start with 30-minute intervals
   - Adjust based on release frequency
   - Consider rate limiting

## 📊 Cost Analysis

### Docker Hub (Current)
- **Cost**: Free
- **Limitations**: 10 pulls/hour for anonymous users
- **Risk**: Rate limiting could affect users

### GHCR (Recommended)
- **Cost**: Free
- **Limitations**: None for public packages
- **Risk**: Minimal (backed by GitHub/Microsoft)

### Self-Hosted Options
- **Cost**: Server costs ($5-20/month)
- **Benefits**: Full control, unlimited usage
- **Complexity**: High maintenance overhead

## 🎯 Recommended Solution

### Immediate (Next 1-2 hours):
1. **Enable scheduled automation** in existing `check-upstream-releases.yml`
2. **Test with current Docker Hub setup**
3. **Verify builds trigger automatically**

### Short-term (Next week):
1. **Consider switching to GHCR** for better limits
2. **Add build notifications**
3. **Document the process**

### Long-term (Future):
1. **Monitor usage patterns**
2. **Evaluate self-hosted options** if needed
3. **Optimize build frequency**

## 🔧 Implementation Commands

### Enable Scheduled Automation:
```bash
# Update the workflow file
git checkout fix-docker-ci-workflow
# Edit .github/workflows/check-upstream-releases.yml
# Add cron schedule and improve logic
git add .github/workflows/check-upstream-releases.yml
git commit -m "feat: enable automatic Docker builds on upstream releases"
git push jkfork fix-docker-ci-workflow
```

### Switch to GHCR (Optional):
```bash
# Update docker-publish.yml
# Change REGISTRY to ghcr.io
# Update IMAGE_NAME to jeremiah-k/mmrelay
# Test build
```

## 📋 Success Criteria

- [ ] Docker images build automatically within 30 minutes of main repo releases
- [ ] No manual intervention required for standard releases
- [ ] Build failures are detected and reported
- [ ] Images are properly tagged and available to users
- [ ] No rate limiting issues for end users

---

**Next Steps**: Implement scheduled automation and test with next release
**Estimated Time**: 2-3 hours for full implementation
**Maintenance**: Minimal once set up