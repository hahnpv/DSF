#!/bin/bash
# Helper script to run sixdof examples with the dynamic executable
# Usage: ./run_sixdof_example.sh <example.xml>

set -e

# Roots are derived from this script's own location, never hardcoded: the
# checkouts have moved before (/home/philip/git/* -> /opt/*) and every
# absolute path baked into a script or deck broke when they did. sixdof is
# the sibling repo DSF's build already expects; override for other layouts.
DSF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIXDOF_ROOT="${SIXDOF_ROOT:-$(cd "$DSF_ROOT/../sixdof" 2>/dev/null && pwd)}"
BUILD_DIR="$DSF_ROOT/build"
SIXDOF_BUILD="$SIXDOF_ROOT/build"
DYNAMIC_EXE="$BUILD_DIR/examples/dynamic/dynamic"

# Decks name the model library by bare soname (library="libsixdof.so"), so
# the dynamic linker resolves it from here — see CLAUDE.md.
export LD_LIBRARY_PATH="$BUILD_DIR:$SIXDOF_BUILD:$LD_LIBRARY_PATH"

if [ ! -f "$DYNAMIC_EXE" ]; then
    echo "Error: dynamic executable not found at $DYNAMIC_EXE"
    echo "Please build first: make -C $BUILD_DIR -j\$(nproc)"
    exit 1
fi

if [ ! -f "$SIXDOF_BUILD/libsixdof.so" ]; then
    echo "Error: libsixdof.so not found at $SIXDOF_BUILD/libsixdof.so"
    echo "Please build sixdof first, or set SIXDOF_ROOT to its checkout."
    exit 1
fi

# If no argument provided, show available examples
if [ $# -eq 0 ]; then
    echo "Usage: $0 <example.xml>"
    echo ""
    echo "Available examples in $SIXDOF_ROOT/examples:"
    find "$SIXDOF_ROOT/examples" -name '*.xml' -printf '  %P\n' 2>/dev/null | sort \
        || echo "  No .xml files found"
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

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "Error: Example file not found: $EXAMPLE_FILE"
    exit 1
fi

EXAMPLE_FILE="$(cd "$(dirname "$EXAMPLE_FILE")" && pwd)/$(basename "$EXAMPLE_FILE")"

echo "======================================"
echo "Running sixdof example: $(basename "$EXAMPLE_FILE")"
echo "Library path: $LD_LIBRARY_PATH"
echo "======================================"
echo ""

# Run the deck IN PLACE. It used to be copied to a temp file with its
# library path rewritten; decks now name the library by soname, and running
# from the deck's own directory is what makes its relative data references
# (aero tables, terrain) resolve.
cd "$(dirname "$EXAMPLE_FILE")"
"$DYNAMIC_EXE" "$EXAMPLE_FILE"
