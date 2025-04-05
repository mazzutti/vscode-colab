#!/bin/bash
set -e

# Ensure clean working directory
if [[ $(git status --porcelain) ]]; then
  echo "Working directory not clean. Commit or stash changes first."
  exit 1
fi

# Get current version from setup.cfg
CURRENT_VERSION=$(grep "version =" setup.cfg | sed 's/version = //')
echo "Current version: $CURRENT_VERSION"

# Ask for new version
read -p "Enter new version: " NEW_VERSION

# Update version in setup.cfg
sed -i "s/version = $CURRENT_VERSION/version = $NEW_VERSION/" setup.cfg

# Build package
rm -rf dist/ build/ *.egg-info/
python -m build

# Commit and tag
git add setup.cfg
git commit -m "Bump version to $NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Version $NEW_VERSION"

# Push changes
git push origin main
git push origin "v$NEW_VERSION"

# Upload to PyPI
python -m twine upload dist/*

echo "Released version $NEW_VERSION"