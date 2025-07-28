#!/usr/bin/env python3
"""
Version bumping script for MMRelay.

This script updates the version number in the single source of truth location.
All other systems (setup.py, Docker workflows, etc.) automatically reference this version.

Single source of truth:
- src/mmrelay/__init__.py (__version__ variable)

All other locations automatically reference this:
- setup.py imports __version__ from mmrelay module
- GitHub workflows extract version from mmrelay module
- CLI and runtime use imported __version__

Usage:
    python scripts/bump_version.py <new_version>

Example:
    python scripts/bump_version.py 1.2.0
"""

import argparse
import re
import sys
from pathlib import Path


def update_file(file_path: Path, pattern: str, replacement: str, description: str):
    """Update a file with the new version using regex pattern."""
    try:
        content = file_path.read_text()
        new_content = re.sub(pattern, replacement, content)

        if content != new_content:
            file_path.write_text(new_content)
            print(f"✅ Updated {description}: {file_path}")
            return True
        else:
            print(f"⚠️  No changes needed in {description}: {file_path}")
            return False
    except Exception as e:
        print(f"❌ Error updating {description} in {file_path}: {e}")
        return False


def bump_version(new_version: str):
    """Update version in the single source of truth location."""
    print(f"🚀 Bumping version to {new_version}")

    # Validate version format (basic semver check)
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print("❌ Version must be in format X.Y.Z (e.g., 1.2.0)")
        return False

    root_dir = Path(__file__).parent.parent
    updates_made = 0

    # Update the single source of truth: __init__.py
    init_py = root_dir / "src/mmrelay/__init__.py"
    if update_file(
        init_py,
        r'__version__ = "[^"]*"',
        f'__version__ = "{new_version}"',
        "mmrelay module version (single source of truth)",
    ):
        updates_made += 1

    # Verify that all other systems will pick up the change
    print("\n📋 Version will be automatically used by:")
    print("  • setup.py (imports __version__ from mmrelay)")
    print("  • Docker workflows (extract from mmrelay module)")
    print("  • ARMv7 PYZ workflow (extract from mmrelay module)")
    print("  • Windows packaging (extract from mmrelay module)")
    print("  • CLI --version command (imports __version__)")
    print("  • Runtime version checks (imports __version__)")

    print(f"\n🎉 Version bump complete! Made {updates_made} updates.")

    if updates_made > 0:
        print("\n📝 Next steps:")
        print("1. Review the changes with: git diff")
        print("2. Test the version: python -c \"import sys; sys.path.insert(0, 'src'); from mmrelay import __version__; print(__version__)\"")
        print("3. Test the build: python setup.py --version")
        print(
            "4. Commit the changes: git add . && git commit -m 'Bump version to {}'".format(
                new_version
            )
        )
        print("5. Create a tag: git tag v{}".format(new_version))
        print("6. Push changes: git push && git push --tags")

    return updates_made > 0


def main():
    parser = argparse.ArgumentParser(description="Bump version in all MMRelay files")
    parser.add_argument("version", help="New version number (e.g., 1.2.0)")

    args = parser.parse_args()

    success = bump_version(args.version)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
