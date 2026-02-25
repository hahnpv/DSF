"""
test_dsf_xml_equivalence.py
---------------------------
Verify that gps_1hr.dsf and gps_1hr.xml with equivalent settings produce
bitwise-identical values at their common sample timestamps.

Both files represent the same GPS orbit; the DSF is run via `dsf run` (which
converts it to XML internally). Both use file=100.0 (output every 100 sim-s),
so their record counts should also match.
"""
import numpy as np
import pytest


# xml_h5 and dsf_h5 are session-scoped subprocess fixtures from conftest.py.
# Each runs the GPS 1-hour simulation via 'dsf run --h5'.

def _common_indices(times_a: np.ndarray, times_b: np.ndarray):
    """Index pairs where both time arrays share a timestamp (to 1µs tolerance)."""
    ia, ib = [], []
    for i, t in enumerate(times_a):
        j = np.searchsorted(times_b, t)
        if j < len(times_b) and abs(times_b[j] - t) < 1e-6:
            ia.append(i)
            ib.append(j)
    return np.array(ia), np.array(ib)


class TestDsfXmlEquivalence:

    def test_same_block_ids(self, xml_h5, dsf_h5):
        """Both outputs must have the same top-level groups (block IDs)."""
        _, data_xml = xml_h5
        _, data_dsf = dsf_h5
        assert set(data_xml.keys()) == set(data_dsf.keys()), (
            f"Block mismatch: XML={set(data_xml.keys())} DSF={set(data_dsf.keys())}"
        )

    def test_same_dataset_names(self, xml_h5, dsf_h5):
        """Within each block the same property names must be present."""
        _, data_xml = xml_h5
        _, data_dsf = dsf_h5
        for block_id in data_xml:
            assert set(data_xml[block_id].keys()) == set(data_dsf[block_id].keys()), (
                f"Property mismatch in block '{block_id}'"
            )

    def test_same_timestep_count(self, xml_h5, dsf_h5):
        """Both runs must produce the same number of time samples."""
        times_xml, _ = xml_h5
        times_dsf, _ = dsf_h5
        assert len(times_xml) == len(times_dsf), (
            f"Record count: XML={len(times_xml)} DSF={len(times_dsf)}"
        )

    def test_time_arrays_identical(self, xml_h5, dsf_h5):
        times_xml, _ = xml_h5
        times_dsf, _ = dsf_h5
        np.testing.assert_array_equal(times_xml, times_dsf)

    def test_all_properties_identical(self, xml_h5, dsf_h5):
        """At common timestamps every numeric dataset must be bitwise identical."""
        times_xml, data_xml = xml_h5
        times_dsf, data_dsf = dsf_h5
        ia, ib = _common_indices(times_xml, times_dsf)
        assert len(ia) >= 5, f"Too few common timestamps: {len(ia)}"
        for block_id, props in data_xml.items():
            for prop_name, arr_xml in props.items():
                arr_dsf = data_dsf[block_id][prop_name]
                np.testing.assert_array_equal(
                    arr_xml[ia], arr_dsf[ib],
                    err_msg=f"Mismatch in {block_id}/{prop_name} at common timestamps"
                )
