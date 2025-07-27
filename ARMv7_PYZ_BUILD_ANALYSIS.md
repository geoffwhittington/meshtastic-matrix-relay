# ARMv7 PYZ Build Analysis - rpds-py Compilation Issues

**Date**: July 27, 2025  
**Issue**: `ModuleNotFoundError: No module named 'rpds.rpds'` in ARMv7 PYZ builds  
**Status**: Under Investigation  

## 🚨 Problem Statement

The ARMv7 PYZ builds are failing at runtime with a missing `rpds.rpds` module error, despite the build process completing successfully. This prevents the MMRelay application from starting on ARMv7 devices like the femtofox.

### Error Details
```
ModuleNotFoundError: No module named 'rpds.rpds'
```

**Error Location**: 
```python
File "rpds/__init__.py", line 1, in <module>
    from .rpds import *
```

**Dependency Chain**:
```
mmrelay → matrix-nio → jsonschema (≥4.0) → referencing → rpds-py (Rust-based)
```

## 🔍 Technical Analysis

### Root Cause Identification

1. **rpds-py Package Nature**:
   - Python bindings to Rust `rpds` crate
   - Requires compilation via `maturin` (Rust-Python bridge)
   - Contains both Python wrapper code and compiled Rust binary

2. **Cross-Compilation Challenge**:
   - ARMv7 target: `armv7-unknown-linux-gnueabihf`
   - QEMU emulation environment in CI
   - Complex toolchain requirements for Rust cross-compilation

3. **Build vs Runtime Discrepancy**:
   - Build appears successful (no compilation errors)
   - Python wrapper installs correctly
   - Rust binary component missing or incompatible

### Current Build Environment

**Docker Image**: `arm32v7/python:3.11`  
**Emulation**: QEMU via `--platform linux/arm/v7`  
**Rust Setup**: `rustup` with default stable toolchain  

**Current Workflow Steps**:
1. Install system dependencies (gcc, libffi-dev, etc.)
2. Install Rust via rustup
3. Install Python build tools (pip, setuptools, wheel, maturin)
4. **Workaround**: Pin `jsonschema<4.0.0` and `referencing<0.30.0`
5. Install requirements and build PYZ

## 📚 Historical Context

### Previous Attempts (Git History Analysis)

**Commit 7099872** (April 11, 2025):
- Updated Cargo config for sparse index (Rust ≥1.86)
- Fixed registry configuration format
```toml
[source.crates-io]
replace-with = "sparse-index"
[source.sparse-index]
registry = "sparse+https://index.crates.io/"
```

**Commit 01c6658**:
- Added rustup installation
- Improved build verification steps
- Added native .so file verification

**Multiple iterations** focused on:
- Cargo configuration fixes
- Rust toolchain setup
- Build environment improvements
- Dependency version pinning as workaround

### Current Workaround Strategy

The build currently avoids the issue by pinning older versions:
```bash
pip install "jsonschema<4.0.0" "referencing<0.30.0"
```

This prevents `rpds-py` from being required but limits functionality and creates technical debt.

## 🔬 Research Findings

### rpds-py Package Analysis

**Package Details**:
- **Purpose**: Python bindings to Rust rpds (Rust Persistent Data Structures)
- **Build System**: maturin (PEP 517 compliant)
- **Rust Dependency**: Yes, requires Rust compiler
- **Cross-Compilation**: Known to be challenging

**Ecosystem Impact**:
- Required by jsonschema ≥4.18
- Increasingly common in Python ecosystem
- Critical for modern JSON schema validation

### Cross-Compilation Research

**Successful Patterns Found**:
1. **Yocto/OpenEmbedded**: Has working rpds-py recipes
2. **Native ARM Builders**: GitHub ARM runners
3. **Pre-built Wheels**: Some distributions provide ARM wheels

**Common Issues**:
- Missing Rust target for ARMv7
- Incorrect linker configuration
- Environment variable setup
- QEMU emulation limitations

## 💡 Solution Strategies

### 🥇 Strategy 1: Enhanced Cross-Compilation Setup

**Approach**: Fix the cross-compilation environment to properly build rpds-py

**Implementation**:
```yaml
- name: Setup ARMv7 Cross-Compilation
  run: |
    # Install cross-compilation toolchain
    apt-get install -y gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf
    
    # Add ARMv7 Rust target
    rustup target add armv7-unknown-linux-gnueabihf
    
    # Configure environment for cross-compilation
    export CARGO_TARGET_ARMV7_UNKNOWN_LINUX_GNUEABIHF_LINKER=arm-linux-gnueabihf-gcc
    export CC_armv7_unknown_linux_gnueabihf=arm-linux-gnueabihf-gcc
    export CXX_armv7_unknown_linux_gnueabihf=arm-linux-gnueabihf-g++
    export PKG_CONFIG_ALLOW_CROSS=1
    
    # Force build from source
    pip install rpds-py --no-binary=rpds-py
```

**Pros**:
- Addresses root cause
- Maintains full functionality
- Future-proof solution

**Cons**:
- Complex setup
- May increase build time
- Requires testing and validation

### 🥈 Strategy 2: Pre-built Wheel Caching

**Approach**: Build rpds-py wheel once and cache for reuse

**Implementation**:
```yaml
- name: Cache rpds-py wheel
  uses: actions/cache@v3
  with:
    path: ~/rpds-py-wheels
    key: rpds-py-armv7-${{ hashFiles('requirements.txt') }}

- name: Build or use cached rpds-py
  run: |
    if [ ! -f ~/rpds-py-wheels/rpds_py-*.whl ]; then
      # Build wheel with proper cross-compilation
      pip wheel rpds-py --wheel-dir ~/rpds-py-wheels --no-binary=rpds-py
    fi
    pip install ~/rpds-py-wheels/rpds_py-*.whl
```

**Pros**:
- Faster subsequent builds
- Isolates compilation complexity
- Reusable across builds

**Cons**:
- Initial setup complexity
- Cache management overhead
- Version update challenges

### 🥉 Strategy 3: Native ARM Builder

**Approach**: Use actual ARM hardware or native ARM runners

**Implementation**:
```yaml
runs-on: [self-hosted, linux, arm64]
# OR
runs-on: ubuntu-latest-arm
```

**Pros**:
- No emulation overhead
- Native compilation environment
- Likely to work correctly

**Cons**:
- Requires ARM runners (cost/availability)
- Different from current infrastructure
- May need runner setup

### 🏅 Strategy 4: Alternative Dependency Path

**Approach**: Modify dependency chain to avoid rpds-py

**Options**:
1. Fork matrix-nio to use older jsonschema
2. Find alternative JSON schema library
3. Implement minimal schema validation

**Pros**:
- Avoids compilation issues entirely
- Maintains current build process
- Immediate solution

**Cons**:
- Technical debt
- Maintenance burden
- Potential functionality loss

## 🛠️ Recommended Implementation Plan

### Phase 1: Enhanced Cross-Compilation (Immediate)

1. **Create test branch** with enhanced cross-compilation setup
2. **Add proper Rust target** and toolchain configuration
3. **Test rpds-py compilation** in isolation
4. **Validate full build process**

### Phase 2: Development Environment Setup

1. **Local cross-compilation setup** for faster iteration
2. **Docker development environment** matching CI
3. **Testing framework** for ARMv7 validation

### Phase 3: Production Implementation

1. **Update CI workflow** with working solution
2. **Remove version pinning workaround**
3. **Full regression testing**
4. **Documentation updates**

## 🧪 Testing Strategy

### Local Testing Environment

```bash
# Setup local ARMv7 cross-compilation
docker run --platform linux/arm/v7 -it arm32v7/python:3.11 bash

# Inside container:
apt-get update && apt-get install -y gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source ~/.cargo/env
rustup target add armv7-unknown-linux-gnueabihf

# Test rpds-py compilation
export CARGO_TARGET_ARMV7_UNKNOWN_LINUX_GNUEABIHF_LINKER=arm-linux-gnueabihf-gcc
export CC_armv7_unknown_linux_gnueabihf=arm-linux-gnueabihf-gcc
export CXX_armv7_unknown_linux_gnueabihf=arm-linux-gnueabihf-g++
export PKG_CONFIG_ALLOW_CROSS=1
pip install rpds-py --no-binary=rpds-py -v
```

### Validation Tests

1. **Import Test**: `python -c "from rpds import HashTrieMap"`
2. **Functionality Test**: Basic rpds operations
3. **Integration Test**: Full mmrelay startup
4. **Performance Test**: Build time comparison

## 📊 Success Metrics

- [ ] ARMv7 PYZ builds complete without errors
- [ ] `rpds.rpds` module imports successfully
- [ ] Full matrix-nio functionality preserved
- [ ] Build time remains under 2 hours
- [ ] Runtime performance acceptable on ARMv7 hardware

## 🔗 References and Resources

### Technical Documentation
- [maturin cross-compilation guide](https://github.com/PyO3/maturin)
- [Rust cross-compilation book](https://rust-lang.github.io/rustup/cross-compilation.html)
- [rpds-py GitHub repository](https://github.com/crate-ci/rpds-py)

### Related Issues
- [Yocto rpds-py recipe](https://layers.openembedded.org/)
- [Cross-compilation discussions](https://github.com/PyO3/maturin/issues)

### Build Environment
- Current workflow: `.github/workflows/build-pyz-armv7.yml`
- Docker image: `arm32v7/python:3.11`
- QEMU platform: `linux/arm/v7`

## 📝 Next Actions

1. **Implement Strategy 1** (Enhanced Cross-Compilation)
2. **Create test branch** with proposed changes
3. **Set up local development environment**
4. **Document results** and iterate

---

## 🐳 Docker Registry Options Analysis

### Current Setup
- **Registry**: Docker Hub (docker.io)
- **Username**: tadchilly
- **Repository**: tadchilly/mmrelay
- **Status**: Working, but manual triggers only

### Docker Hub Free Tier Limits
- **Public repositories**: Unlimited
- **Private repositories**: 1 free
- **Pull rate limits**: 100 pulls/hour for authenticated users, 10 pulls/hour for anonymous
- **Push limits**: No specific limits on pushes for free accounts
- **Storage**: No specific limits for public repositories

### Free Alternative Registries

#### 1. GitHub Container Registry (GHCR) - **RECOMMENDED**
- **URL**: ghcr.io
- **Free tier**: Unlimited for public packages
- **Benefits**:
  - Integrated with GitHub (same authentication)
  - No pull rate limits for public images
  - Automatic cleanup policies available
  - Better integration with GitHub Actions
- **Format**: `ghcr.io/jeremiah-k/mmrelay:tag`

#### 2. Quay.io (Red Hat)
- **Free tier**: Unlimited public repositories
- **Benefits**: Advanced security scanning, build triggers
- **Considerations**: Requires separate account management

#### 3. GitLab Container Registry
- **Free tier**: 10GB storage for public projects
- **Benefits**: Integrated CI/CD, automatic cleanup

### Automation Solutions

#### Option 1: Repository Dispatch (Current Setup)
- **Status**: Partially implemented in `check-upstream-releases.yml`
- **Limitation**: Requires manual trigger or scheduled runs
- **Benefit**: Works across different repository owners

#### Option 2: GitHub App/Webhook
- **Complexity**: High
- **Benefit**: True automation on release events
- **Limitation**: Requires app installation on main repo

#### Option 3: Scheduled Monitoring (Recommended)
- **Implementation**: Cron-based workflow that checks for new releases
- **Frequency**: Every 30 minutes or hourly
- **Benefit**: Fully automated, no main repo changes needed

---

**Last Updated**: July 27, 2025
**Next Review**: After Strategy 1 implementation
**Assigned**: Development Team