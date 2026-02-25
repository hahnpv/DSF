"""
test_map_widget.py
------------------
Unit tests for MapWidget and MapWindow using pytest-qt.
No display-level rendering is triggered; we test data paths only.
"""
import math
import sys
import os
import pytest
import numpy as np

pytestmark = pytest.mark.qt  # marks as requiring a QApplication


@pytest.fixture
def map_win(qtbot):
    from dsf.gui.ui.map_window import MapWindow
    win = MapWindow()
    qtbot.addWidget(win)
    return win


@pytest.fixture
def map_widget(map_win):
    return map_win.map_widget


class TestMapWidgetDataPaths:

    def _make_frame(self, lat_deg: float, lon_deg: float) -> dict:
        """Build a single frame dict the way map_view.py does."""
        return {
            "TestBlock": {
                "lambda_d":   math.radians(lat_deg),
                "l_i_earth":  math.radians(lon_deg),
                "altitude":   500_000.0,
            }
        }

    def test_update_populates_vehicle_positions(self, map_widget):
        """After one update, the block should appear in vehicle_positions."""
        map_widget.max_history = 10
        map_widget.update_deep_data(0.0, self._make_frame(45.0, -90.0))
        assert "TestBlock" in map_widget.vehicle_positions

    def test_position_values_correct(self, map_widget):
        """Lat/lon should be converted to degrees correctly."""
        map_widget.max_history = 10
        map_widget.update_deep_data(0.0, self._make_frame(45.0, -90.0))
        lat, lon = map_widget.vehicle_positions["TestBlock"]
        assert abs(lat - 45.0) < 1e-10
        assert abs(lon - (-90.0)) < 1e-10

    def test_history_grows_with_frames(self, map_widget):
        """History list must accumulate one entry per update call."""
        map_widget.max_history = 100
        for i in range(10):
            map_widget.update_deep_data(float(i), self._make_frame(i, i))
        assert len(map_widget.vehicle_history["TestBlock"]) == 10

    def test_max_history_truncates(self, map_widget):
        """History must not exceed max_history."""
        map_widget.max_history = 5
        for i in range(20):
            map_widget.update_deep_data(float(i), self._make_frame(i, i))
        assert len(map_widget.vehicle_history["TestBlock"]) <= 5

    def test_full_trails_checkbox_changes_limit(self, map_widget):
        """Checking 'Full Trails' must raise max_history substantially."""
        before = map_widget.max_history
        map_widget.full_trails_cb.setChecked(True)
        assert map_widget.max_history > before

    def test_reset_clears_positions(self, map_widget):
        """reset() must clear all vehicle state."""
        map_widget.max_history = 10
        map_widget.update_deep_data(0.0, self._make_frame(10.0, 20.0))
        map_widget.reset()
        assert len(map_widget.vehicle_positions) == 0
        assert len(map_widget.vehicle_history) == 0

    def test_replay_sets_max_history_to_n_frames(self, map_win):
        """Simulating the map_view replay mode: pre-set max_history = len(times)."""
        N = 100
        map_win.map_widget.max_history = N
        for i in range(N):
            map_win.update_deep_data(float(i), self._make_frame(i % 90, i % 180))
        assert len(map_win.map_widget.vehicle_history["TestBlock"]) == N
