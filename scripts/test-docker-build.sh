#!/bin/bash

# Script to test Docker builds for specific releases
# This allows testing the Docker workflow without creating new releases

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Configuration
REGISTRY="ghcr.io"
IMAGE_NAME="jeremiah-k/mmrelay"
TEST_TAG_PREFIX="test"

# Default values
VERSION=""
PLATFORMS="linux/amd64,linux/arm64"
PUSH_IMAGE=false
DRY_RUN=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Test Docker builds for MMRelay releases"
    echo ""
    echo "Options:"
    echo "  -v, --version VERSION    Version to build (e.g., 1.1.3, latest)"
    echo "  -p, --platforms PLATFORMS  Platforms to build for (default: linux/amd64,linux/arm64)"
    echo "  --push                   Push the built image to registry"
    echo "  --dry-run                Show what would be done without actually building"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -v 1.1.3              # Test build for version 1.1.3"
    echo "  $0 -v 1.1.3 --push       # Build and push test image for 1.1.3"
    echo "  $0 -v latest --dry-run    # Show what would be done for latest"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -p|--platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$VERSION" ]; then
    print_error "Version is required. Use -v or --version to specify."
    show_usage
    exit 1
fi

# Check if Docker buildx is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker buildx version &> /dev/null; then
    print_error "Docker buildx is not available"
    exit 1
fi

# Generate build information
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse HEAD)
GIT_SHA=$(git rev-parse --short HEAD)

# Determine tag strategy
if [ "$VERSION" = "latest" ]; then
    # For latest, use current version from code
    CODE_VERSION=$(python3 -c "import sys; sys.path.insert(0, 'src'); from mmrelay import __version__; print(__version__)" 2>/dev/null || echo "unknown")
    DOCKER_TAG="$TEST_TAG_PREFIX-$CODE_VERSION-$GIT_SHA"
    TAG_LATEST=true
else
    # For specific version, use that version
    DOCKER_TAG="$TEST_TAG_PREFIX-$VERSION-$GIT_SHA"
    TAG_LATEST=false
fi

# Build the full image name
FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$DOCKER_TAG"

print_header "Docker Build Test Configuration"
echo "Version: $VERSION"
echo "Docker Tag: $DOCKER_TAG"
echo "Full Image: $FULL_IMAGE_NAME"
echo "Platforms: $PLATFORMS"
echo "Push Image: $PUSH_IMAGE"
echo "Tag Latest: $TAG_LATEST"
echo "Build Date: $BUILD_DATE"
echo "VCS Ref: $VCS_REF"
echo "Git SHA: $GIT_SHA"
echo ""

if [ "$DRY_RUN" = true ]; then
    print_warning "DRY RUN MODE - No actual build will be performed"
    echo ""
    echo "Would execute:"
    echo "docker buildx build \\"
    echo "  --platform $PLATFORMS \\"
    if [ "$PUSH_IMAGE" = true ]; then
        echo "  --push \\"
    else
        echo "  --load \\"
    fi
    echo "  --build-arg BUILD_DATE=$BUILD_DATE \\"
    echo "  --build-arg VCS_REF=$VCS_REF \\"
    echo "  --build-arg VERSION=$VERSION \\"
    echo "  --tag $FULL_IMAGE_NAME \\"
    if [ "$TAG_LATEST" = true ] && [ "$PUSH_IMAGE" = true ]; then
        echo "  --tag $REGISTRY/$IMAGE_NAME:$TEST_TAG_PREFIX-latest \\"
    fi
    echo "  ."
    exit 0
fi

# Ensure buildx builder exists
print_status "Setting up Docker buildx builder..."
if ! docker buildx inspect multiarch &> /dev/null; then
    print_status "Creating multiarch builder..."
    docker buildx create --name multiarch --use --bootstrap
else
    print_status "Using existing multiarch builder..."
    docker buildx use multiarch
fi

# Build the image
print_status "Starting Docker build..."
BUILD_ARGS=(
    "--platform" "$PLATFORMS"
    "--build-arg" "BUILD_DATE=$BUILD_DATE"
    "--build-arg" "VCS_REF=$VCS_REF"
    "--build-arg" "VERSION=$VERSION"
    "--tag" "$FULL_IMAGE_NAME"
)

# Add latest tag if requested and pushing
if [ "$TAG_LATEST" = true ] && [ "$PUSH_IMAGE" = true ]; then
    BUILD_ARGS+=("--tag" "$REGISTRY/$IMAGE_NAME:$TEST_TAG_PREFIX-latest")
fi

# Add push or load flag
if [ "$PUSH_IMAGE" = true ]; then
    BUILD_ARGS+=("--push")
    print_warning "Image will be pushed to registry: $REGISTRY/$IMAGE_NAME"
else
    # For multi-platform builds, we can't use --load, so we'll just build
    if [[ "$PLATFORMS" == *","* ]]; then
        print_warning "Multi-platform build - image will only be cached (use --push to publish)"
    else
        BUILD_ARGS+=("--load")
        print_status "Single platform build - image will be loaded locally"
    fi
fi

# Add context
BUILD_ARGS+=(".")

# Execute the build
print_status "Executing: docker buildx build ${BUILD_ARGS[*]}"
if docker buildx build "${BUILD_ARGS[@]}"; then
    print_status "Build completed successfully!"
    
    if [ "$PUSH_IMAGE" = true ]; then
        print_status "Image pushed to: $FULL_IMAGE_NAME"
        if [ "$TAG_LATEST" = true ]; then
            print_status "Also tagged as: $REGISTRY/$IMAGE_NAME:$TEST_TAG_PREFIX-latest"
        fi
    else
        if [[ "$PLATFORMS" != *","* ]]; then
            print_status "Image available locally as: $FULL_IMAGE_NAME"
            print_status "Test with: docker run --rm $FULL_IMAGE_NAME --help"
        fi
    fi
else
    print_error "Build failed!"
    exit 1
fi

print_header "Build Summary"
echo "✅ Successfully built Docker image for version $VERSION"
echo "📦 Image: $FULL_IMAGE_NAME"
echo "🏗️  Platforms: $PLATFORMS"
if [ "$PUSH_IMAGE" = true ]; then
    echo "🚀 Status: Pushed to registry"
else
    echo "💾 Status: Built locally"
fi
