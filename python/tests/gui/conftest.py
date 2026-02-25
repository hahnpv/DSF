"""
GUI test conftest — provides the QApplication and qtbot fixtures.
Globe tests are skipped when no $DISPLAY is available.
"""
import os
import pytest

# Skip globe tests globally when headless
def pytest_collection_modifyitems(config, items):
    if not os.environ.get("DISPLAY"):
        skip_globe = pytest.mark.skip(reason="No $DISPLAY — skipping globe/pyvista tests")
        for item in items:
            if "globe" in item.nodeid:
                item.add_marker(skip_globe)
