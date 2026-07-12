#!/bin/bash
# Helper script to run sixdof examples with the dynamic executable
# Usage: ./run_sixdof_example.sh <example.xml>

set -e

# Setup paths
DSF_ROOT="/home/philip/git/DSF"
SIXDOF_ROOT="/home/philip/git/sixdof"
BUILD_DIR="$DSF_ROOT/build"
DYNAMIC_EXE="$BUILD_DIR/examples/dynamic/dynamic"

# Set library path to include both DSF and sixdof libraries
export LD_LIBRARY_PATH="$BUILD_DIR:$BUILD_DIR/sixdof_build:$LD_LIBRARY_PATH"

# Check if dynamic executable exists
if [ ! -f "$DYNAMIC_EXE" ]; then
    echo "Error: dynamic executable not found at $DYNAMIC_EXE"
    echo "Please build first: make -C $BUILD_DIR -j\$(nproc)"
    exit 1
fi

# Check if libsixdof.so exists
if [ ! -f "$BUILD_DIR/sixdof_build/libsixdof.so" ]; then
    echo "Error: libsixdof.so not found at $BUILD_DIR/sixdof_build/libsixdof.so"
    echo "Please build first: make -C $BUILD_DIR sixdof"
    exit 1
fi

# If no argument provided, show available examples
if [ $# -eq 0 ]; then
    echo "Usage: $0 <example.xml>"
    echo ""
    echo "Available examples in $SIXDOF_ROOT/examples:"
    ls -1 "$SIXDOF_ROOT/examples"/*.xml 2>/dev/null | xargs -n 1 basename || echo "  No .xml files found"
    exit 0
fi

EXAMPLE_FILE="$1"

# If relative path, check test/ then sixdof/examples
if [ ! -f "$EXAMPLE_FILE" ]; then
    if [ -f "test/$1" ]; then
        EXAMPLE_FILE="test/$1"
    elif [ -f "$DSF_ROOT/test/$1" ]; then
        EXAMPLE_FILE="$DSF_ROOT/test/$1"
    else
        EXAMPLE_FILE="$SIXDOF_ROOT/examples/$1"
    fi
fi

# Check if example exists
if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "Error: Example file not found: $EXAMPLE_FILE"
    exit 1
fi

# Create a temporary modified XML file with correct library path
TEMP_XML=$(mktemp --suffix=.xml)
trap "rm -f $TEMP_XML" EXIT

# Replace the library path in the XML
sed "s|library=\"../sixdof/libsixdof.so\"|library=\"$BUILD_DIR/sixdof_build/libsixdof.so\"|g" "$EXAMPLE_FILE" > "$TEMP_XML"

echo "======================================"
echo "Running sixdof example: $(basename $EXAMPLE_FILE)"
echo "Library path: $LD_LIBRARY_PATH"
echo "======================================"
echo ""
echo $DYNAMIC_EXE

# Run the simulation
cd "$(dirname $EXAMPLE_FILE)"
"$DYNAMIC_EXE" "$TEMP_XML"
