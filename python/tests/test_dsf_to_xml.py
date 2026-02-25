"""
test_dsf_to_xml.py
------------------
Verify that convert_dsf_to_xml correctly round-trips a .dsf project,
preserving simulation parameters and key orbital elements.
"""
import os
import json
import math
import pytest
import xml.etree.ElementTree as ET

from tests.conftest import GPS_DSF, GPS_XML


@pytest.fixture(scope="module")
def converted_xml_path(tmp_path_factory):
    """Convert gps_1.dsf → XML once per test session."""
    from dsf.utils.convert_dsf_to_xml import convert_dsf_to_xml
    xml_path = convert_dsf_to_xml(GPS_DSF)
    yield xml_path
    if os.path.exists(xml_path):
        os.remove(xml_path)


@pytest.fixture(scope="module")
def converted_tree(converted_xml_path):
    tree = ET.parse(converted_xml_path)
    return tree.getroot()   # <sim> element


@pytest.fixture(scope="module")
def reference_tree():
    tree = ET.parse(GPS_XML)
    return tree.getroot()


@pytest.fixture(scope="module")
def dsf_meta():
    with open(GPS_DSF) as f:
        data = json.load(f)
    return data["metadata"]


class TestDsfToXmlConversion:

    def test_converted_xml_is_valid(self, converted_xml_path):
        """The generated file must parse as valid XML."""
        tree = ET.parse(converted_xml_path)
        assert tree.getroot() is not None

    def test_sim_element_exists(self, converted_tree):
        assert converted_tree.tag == "sim", f"Root tag is '{converted_tree.tag}', expected 'sim'"

    def test_dt_preserved(self, converted_tree, dsf_meta):
        assert float(converted_tree.get("dt")) == pytest.approx(dsf_meta["dt"])

    def test_tmax_preserved(self, converted_tree, dsf_meta):
        assert float(converted_tree.get("tmax")) == pytest.approx(dsf_meta["tmax"])

    def test_library_preserved(self, converted_tree, dsf_meta):
        lib_xml = converted_tree.get("library", "")
        lib_dsf = dsf_meta.get("library", "")
        assert lib_xml == lib_dsf, f"library: XML='{lib_xml}' DSF='{lib_dsf}'"

    def test_vehicle_block_present(self, converted_tree):
        vehicles = converted_tree.findall(".//vehicle") + converted_tree.findall(".//Vehicle")
        assert len(vehicles) >= 1, "No <vehicle> element found in converted XML"

    def test_equinoctial_block_present(self, converted_tree):
        eom = (converted_tree.findall(".//rbeom")
               + converted_tree.findall(".//Equinoctial"))
        assert len(eom) >= 1, "No <rbeom> / Equinoctial element in converted XML"

    def test_orbital_eccentricity_preserved(self, converted_tree):
        """Eccentricity from state child element must be preserved to full precision."""
        eccentricity_el = converted_tree.find(".//eccentricity")
        assert eccentricity_el is not None, "<eccentricity> element not found"
        val = float(eccentricity_el.text.strip())
        expected = 0.015653435282672032
        assert math.isclose(val, expected, rel_tol=1e-9), (
            f"Eccentricity {val} != {expected}"
        )

    def test_semimajor_axis_preserved(self, converted_tree):
        a_el = converted_tree.find(".//semimajor_axis")
        assert a_el is not None, "<semimajor_axis> element not found"
        val = float(a_el.text.strip())
        expected = 26558762.943163067
        assert math.isclose(val, expected, rel_tol=1e-9), (
            f"Semimajor axis {val} != {expected}"
        )

    def test_inclination_preserved(self, converted_tree):
        inc_el = converted_tree.find(".//inclination")
        assert inc_el is not None
        val = float(inc_el.text.strip())
        assert math.isclose(val, 54.716471105314504, rel_tol=1e-9)
