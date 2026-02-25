"""
test_globe_headless.py
----------------------
Tests for GlobePlotter using PyVista's off-screen backend.
Skipped automatically when $DISPLAY is not set (see gui/conftest.py).
"""
import os
import pytest
import numpy as np


@pytest.fixture(scope="module", autouse=True)
def pyvista_offscreen():
    """Force PyVista into off-screen mode for headless CI."""
    import pyvista as pv
    pv.OFF_SCREEN = True
    pv.global_theme.allow_empty_mesh = True
    yield


@pytest.fixture
def gp():
    """Create a GlobePlotter in non-separate-process mode."""
    from dsf.visualization.globe import GlobePlotter
    plotter = GlobePlotter(distinct_window=False)
    yield plotter
    plotter.close()


# Synthetic circular orbit in ECEF (equatorial, 10 points)
@pytest.fixture
def synthetic_xyz():
    R = 26_558_000.0  # GPS MEO radius [m]
    t = np.linspace(0, 2 * np.pi, 10, endpoint=False)
    return np.column_stack([R * np.cos(t), R * np.sin(t), np.zeros(len(t))])


class TestGlobePlotter:

    def test_add_trajectory_no_exception(self, gp, synthetic_xyz):
        """add_trajectory must not raise."""
        gp.add_trajectory(synthetic_xyz, name="TestTraj", color="cyan")

    def test_add_ground_track_no_exception(self, gp, synthetic_xyz):
        """add_ground_track must not raise."""
        gp.add_trajectory(synthetic_xyz, name="T1")
        gp.add_ground_track(synthetic_xyz, name="GndTrack", color="yellow")

    def test_plotter_has_actors_after_add(self, gp, synthetic_xyz):
        """After adding a trajectory, the plotter must have at least one actor."""
        gp.add_trajectory(synthetic_xyz, name="Traj2", color="magenta")
        actors = gp.plotter.renderer.actors
        assert len(actors) > 0, "No actors added to the plotter"

    def test_multiple_trajectories(self, gp, synthetic_xyz):
        """Adding multiple trajectories must not crash."""
        colors = ["cyan", "red", "lime"]
        for i, c in enumerate(colors):
            gp.add_trajectory(synthetic_xyz, name=f"T{i}", color=c)
