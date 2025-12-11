#!/bin/bash
set -e

# Clean previous builds
rm -rf build dist *.spec

# Build the single-file executable
# --paths .: Add current directory to search path so 'trace' package is found
pyinstaller --onefile \
            --name trace \
            --clean \
            --paths . \
            --hidden-import curses \
            main.py

echo "Build complete. Binary is at dist/trace"
