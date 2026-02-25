"""
test_run_vs_watch.py
--------------------
Verify that `dsf run` (C++ exec loop) and `dsf watch` (Python step loop)
produce identical kinematics at common sample points.

`dsf run` honours rpt=1000 and records sparsely (1 sample per 100 sim-seconds).
`dsf watch` records every step. We compare at the timestamps present in both.
Both commands run in subprocesses (from conftest.py) to avoid DSF/Qt conflicts.
"""
import pytest
import numpy as np


# Properties to verify across run modes
CORE_PROPS = ["Latitude", "Earth Longitude", "altitude", "XYZ_ECEF"]


def _common_indices(times_exec: np.ndarray, times_watch: np.ndarray):
    """
    Return index arrays (i_exec, i_watch) for timestamps present in both sets.
    Searches for each WATCH timestamp in the (denser) exec array.
    """
    i_exec, i_watch = [], []
    for iw, t in enumerate(times_watch):
        ie = np.searchsorted(times_exec, t)
        if ie < len(times_exec) and np.isclose(times_exec[ie], t, rtol=0, atol=1e-9):
            i_exec.append(ie)
            i_watch.append(iw)
    return np.array(i_exec), np.array(i_watch)


class TestRunVsWatch:

    def test_same_block_ids(self, exec_h5, watch_h5):
        _, data_exec  = exec_h5
        _, data_watch = watch_h5
        assert set(data_exec.keys()) == set(data_watch.keys()), (
            f"Block IDs differ: run={set(data_exec)} watch={set(data_watch)}"
        )

    def test_has_common_timestamps(self, exec_h5, watch_h5):
        """There must be at least some timestamps present in both outputs."""
        times_exec, _  = exec_h5
        times_watch, _ = watch_h5
        i_e, i_w = _common_indices(times_exec, times_watch)
        assert len(i_e) >= 10, (
            f"Too few common timestamps: only {len(i_e)} found "
            f"(exec={len(times_exec)} watch={len(times_watch)})"
        )

    @pytest.mark.parametrize("prop", CORE_PROPS)
    def test_core_property_identical_at_common_times(self, exec_h5, watch_h5, prop):
        """
        At timestamps where both run and watch have samples, the values must
        be bitwise identical (same integrator, same initial conditions).
        """
        times_exec, data_exec  = exec_h5
        times_watch, data_watch = watch_h5

        i_e, i_w = _common_indices(times_exec, times_watch)
        if len(i_e) == 0:
            pytest.skip("No common timestamps — skipping")

        for block_id in data_exec:
            if prop in data_exec[block_id] and prop in data_watch.get(block_id, {}):
                arr_exec  = data_exec[block_id][prop][i_e]
                arr_watch = data_watch[block_id][prop][i_w]
                np.testing.assert_array_equal(
                    arr_exec, arr_watch,
                    err_msg=f"{block_id}/{prop}: run vs watch differ at common timestamps",
                )
                return

        pytest.skip(f"Property '{prop}' not found in any block")

    def test_final_state_matches(self, exec_h5, watch_h5):
        """Final recorded state in run must match the corresponding watch state."""
        times_exec, data_exec  = exec_h5
        times_watch, data_watch = watch_h5

        # Find the run's final timestamp in watch output
        t_final = times_exec[-1]
        matches = np.where(np.isclose(times_watch, t_final, rtol=0, atol=1e-9))[0]
        if len(matches) == 0:
            pytest.skip("Final run timestamp not in watch output")

        iw_final = matches[0]
        for block_id in data_exec:
            if "altitude" in data_exec[block_id]:
                alt_exec  = data_exec[block_id]["altitude"][-1]
                alt_watch = data_watch[block_id]["altitude"][iw_final]
                assert alt_exec == alt_watch, (
                    f"Final altitude: run={alt_exec:.4f}  watch={alt_watch:.4f}"
                )
                return
        pytest.skip("No 'altitude' property found")
