#!/bin/bash

# Script to clean up dangling container tags from GitHub Container Registry
# This script specifically targets the dangling tags mentioned:
# - 1.1.3-dev-690ed02
# - 1.1.2-dev-9441413

set -e

# Configuration
OWNER="jeremiah-k"
PACKAGE="mmrelay"
REGISTRY="ghcr.io"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    print_error "GitHub CLI (gh) is not installed. Please install it first:"
    print_error "https://cli.github.com/manual/installation"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    print_error "Not authenticated with GitHub CLI. Please run 'gh auth login' first."
    exit 1
fi

print_status "Starting cleanup of dangling container tags..."

# Specific dangling tags to remove
DANGLING_TAGS=("1.1.3-dev-690ed02" "1.1.2-dev-9441413")

# Function to delete a specific tag
delete_tag() {
    local tag="$1"
    print_status "Looking for tag: $tag"
    
    # Get all package versions and find the one with this tag
    local version_data
    version_data=$(gh api \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/users/$OWNER/packages/container/$PACKAGE/versions" \
        --paginate \
        --jq ".[] | select(.metadata.container.tags[]? == \"$tag\") | {id: .id, tags: .metadata.container.tags}")
    
    if [ -z "$version_data" ]; then
        print_warning "Tag '$tag' not found or already deleted"
        return 0
    fi
    
    local version_id
    version_id=$(echo "$version_data" | jq -r '.id')
    
    print_status "Found tag '$tag' with version ID: $version_id"
    print_status "Tags for this version: $(echo "$version_data" | jq -r '.tags | join(", ")')"
    
    # Confirm deletion
    read -p "Delete tag '$tag' (version ID: $version_id)? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deleting version ID: $version_id"
        if gh api \
            --method DELETE \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "/users/$OWNER/packages/container/$PACKAGE/versions/$version_id"; then
            print_status "Successfully deleted tag '$tag'"
        else
            print_error "Failed to delete tag '$tag'"
            return 1
        fi
    else
        print_warning "Skipped deletion of tag '$tag'"
    fi
}

# Function to list all current tags
list_all_tags() {
    print_status "Current container tags:"
    gh api \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/users/$OWNER/packages/container/$PACKAGE/versions" \
        --paginate \
        --jq '.[] | select(.metadata.container.tags | length > 0) | .metadata.container.tags[]' | sort -u
}

# Function to find and list untagged images
list_untagged_images() {
    print_status "Untagged images:"
    local untagged_count
    untagged_count=$(gh api \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/users/$OWNER/packages/container/$PACKAGE/versions" \
        --paginate \
        --jq '.[] | select(.metadata.container.tags | length == 0)' | jq -s length)
    
    if [ "$untagged_count" -gt 0 ]; then
        print_warning "Found $untagged_count untagged images"
        print_status "You can clean these up using the cleanup-container-registry.yml workflow"
    else
        print_status "No untagged images found"
    fi
}

# Main execution
print_status "Repository: $OWNER/$PACKAGE"
print_status "Registry: $REGISTRY"
echo

# Show current state
list_all_tags
echo
list_untagged_images
echo

# Process each dangling tag
for tag in "${DANGLING_TAGS[@]}"; do
    delete_tag "$tag"
    echo
done

print_status "Cleanup completed!"
print_status "Final state:"
list_all_tags
