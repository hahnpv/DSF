"""
Numerical validation of the physics — ground truth, not self-consistency.

Three families of checks, all through the full stack (deck → `dsf run` → .h5):

1. Kepler closed-form comparison: an equatorial circular orbit under J2 has an
   exact analytic solution (the J2 perturbation is purely radial there), so
   radius and mean motion are checked against closed form.
2. Conservation laws: the WGS84/J2 field is static and axisymmetric, so total
   specific energy (with the J2 potential) and the polar component of specific
   angular momentum are exact invariants of the continuous dynamics; the
   integrator should hold them to near machine precision at GPS altitude.
3. Golden trajectories: frozen reference output committed in fixtures/ for
   both EOM paths (Equinoctial and OblateEarth 6DOF); any change in the
   physics or integration shows up as a diff.

Framework-level integrator checks (convergence order, symplectic energy
behavior, toy two-body) live in test/test_integrators.cpp; these tests cover
what those cannot: the real models, constants, and configuration path.
"""
import json
import math
import os

import numpy as np
import pytest

from tests.conftest import FIXTURES_DIR, require_sixdof, run_sim, load

# Constants as the models define them (DSF/util/math/earth_constants.h and
# sixdof WGS84). Do not "fix" these here — the tests must use exactly what
# the simulation uses, so that deviations measure integration/physics errors,
# not constant mismatches.
MU_EARTH = 3.986004418e14
RE_EARTH = 6378137.0
J2_EQUINOCTIAL = 1.08262982e-3          # dsf::util::earth::J2_EARTH (Equinoctial model)
J2_WGS84 = math.sqrt(5.0) * 4.841668e-4  # -sqrt(5)*C_2_0 (WGS84::gravity)

LEO_XML = os.path.join(FIXTURES_DIR, "leo_equatorial.xml")
GOLDEN_GPS = os.path.join(FIXTURES_DIR, "golden_gps_1hr.json")
GOLDEN_LEO = os.path.join(FIXTURES_DIR, "golden_leo_equatorial.json")


def _block(data, name):
    """Vehicle output group, tolerating both layouts: per-vehicle H5 groups
    and the current root-level contract (sixdof da47f13), where a single
    vehicle's channels load under the loader's flat-file key 'simulation'."""
    if name in data:
        return data[name]
    assert "simulation" in data, \
        f"neither group '{name}' nor flat root output present (keys: {list(data)})"
    return data["simulation"]


def _eci_state(data, group, pos="XYZ", vel="UVW"):
    """(N,3) position, (N,3) velocity from a loaded .h5 dict.

    Dataset names differ by EOM: Equinoctial logs XYZ/UVW, OblateEarth
    logs XYZ_ECI (velocity only in the body frame).
    """
    g = _block(data, group)
    r = np.asarray(g[pos], dtype=float)
    v = np.asarray(g[vel], dtype=float) if vel else None
    return r, v


# ── Session fixture: one LEO run shared by the Kepler tests ─────────────────

@pytest.fixture(scope="session")
def leo_h5(tmp_path_factory):
    """Run leo_equatorial.xml (one full orbit) → (times, data)."""
    require_sixdof()
    d = str(tmp_path_factory.mktemp("leo_run"))
    return load(run_sim(LEO_XML, d))


# ── 1. Kepler comparison (closed form) ──────────────────────────────────────
#
# Equatorial circular orbit at r0: J2 acts purely radially, so the exact
# solution is uniform circular motion with
#   mu_eff = MU * (1 + 1.5*J2*(Re/r0)^2),  n = sqrt(mu_eff/r0^3).
# The fixture's velocity is precomputed for this r0 (see the deck comments).

LEO_R0 = 7378137.0
LEO_MU_EFF = MU_EARTH * (1.0 + 1.5 * J2_WGS84 * (RE_EARTH / LEO_R0) ** 2)


def test_leo_radius_constant(leo_h5):
    """A closed-form circular orbit must stay circular.

    A missing J2 term would leave the launch speed ~0.06% off circular →
    a ±9 km radial oscillation; a J2 sign error → ±18 km. Tolerance of
    10 m is 3 orders below either failure and 4 above observed RK4 error.
    """
    _, data = leo_h5
    r, _ = _eci_state(data, "LEO_Equatorial", pos="XYZ_ECI", vel=None)
    radius = np.linalg.norm(r, axis=1)
    assert np.abs(radius - LEO_R0).max() < 10.0


def test_leo_stays_equatorial(leo_h5):
    """Symmetry: an equatorial orbit must not develop out-of-plane motion."""
    _, data = leo_h5
    r, _ = _eci_state(data, "LEO_Equatorial", pos="XYZ_ECI", vel=None)
    assert np.abs(r[:, 2]).max() < 1.0


def test_leo_mean_motion_matches_analytic(leo_h5):
    """Phase rate over a full orbit vs the closed-form J2 mean motion."""
    times, data = leo_h5
    r, _ = _eci_state(data, "LEO_Equatorial", pos="XYZ_ECI", vel=None)
    theta = np.unwrap(np.arctan2(r[:, 1], r[:, 0]))
    rate = np.polyfit(times, theta, 1)[0]
    n_analytic = math.sqrt(LEO_MU_EFF / LEO_R0 ** 3)
    assert rate == pytest.approx(n_analytic, rel=1e-8)


# ── 2. Conservation laws (GPS orbit, J2 on) ─────────────────────────────────
#
# Uses the session-scoped gps_1hr run (xml_h5 from conftest — no extra sim).
# Drag is zero at GPS altitude (the Equinoctial drag model cuts off at
# 1500 km), so with the static axisymmetric J2 field both quantities below
# are exact invariants.

GPS_GROUP = "GPS_BIIA-23_(PRN_18)"


def _j2_potential(r):
    """Specific potential of the standard J2 field, V(r, phi)."""
    R = np.linalg.norm(r, axis=1)
    sin_phi = r[:, 2] / R
    return -(MU_EARTH / R) * (
        1.0 - 0.5 * J2_EQUINOCTIAL * (RE_EARTH / R) ** 2 * (3.0 * sin_phi ** 2 - 1.0))


def test_gps_energy_conserved(xml_h5):
    """v²/2 + V_J2 is invariant; observed spread is ~2e-14 relative.

    The two-body energy alone (v²/2 − mu/r) oscillates at ~3e-5 relative on
    this orbit, so passing at 1e-10 also confirms the model's J2 force is
    exactly the gradient of the standard J2 potential.
    """
    _, data = xml_h5
    r, v = _eci_state(data, GPS_GROUP)
    E = 0.5 * np.sum(v * v, axis=1) + _j2_potential(r)
    assert np.ptp(E) / abs(E.mean()) < 1e-10


def test_gps_polar_angular_momentum_conserved(xml_h5):
    """h_z = (r × v)_z is invariant in any axisymmetric field."""
    _, data = xml_h5
    r, v = _eci_state(data, GPS_GROUP)
    hz = np.cross(r, v)[:, 2]
    assert np.ptp(hz) / abs(hz.mean()) < 1e-10


def test_gps_elements_bounded(xml_h5):
    """Osculating a, e, i show J2 short-period oscillation but no secular
    drift. Bands are ~3x the observed oscillation amplitudes (688 m,
    3.6e-5, 8.8e-6 rad respectively)."""
    _, data = xml_h5
    g = _block(data, GPS_GROUP)
    assert np.ptp(np.asarray(g["a"])) < 2000.0            # m
    assert np.ptp(np.asarray(g["eccentricity"])) < 1e-4
    assert np.ptp(np.asarray(g["inc"])) < 3e-5            # rad


def test_gps_raan_regresses(xml_h5):
    """J2 makes a prograde orbit's node regress (westward): dRAAN/dt < 0,
    small. Catches a J2 sign error, which would flip the drift."""
    _, data = xml_h5
    raan = np.asarray(_block(data, GPS_GROUP)["RAAN"])
    drift = raan[-1] - raan[0]
    assert drift < 0.0
    assert abs(drift) < 3e-4  # rad over 1 h; secular+short-period is ~5e-5


# ── 3. Golden trajectories ──────────────────────────────────────────────────
#
# References were frozen from a verified build (see git history of the JSON
# files). Tolerances are far above cross-platform FP noise but far below any
# physically meaningful change (e.g. the historical 0.07% J2 constant error).

def _check_golden(times, data, golden_path, rtol, atol_overrides=None):
    with open(golden_path) as f:
        ref = json.load(f)
    group = _block(data, ref["group"]) if ref["group"] else data
    ref_t = np.asarray(ref["time"])
    # Sample the run at the golden timestamps (output cadence must match).
    idx = np.searchsorted(times, ref_t)
    assert np.allclose(times[idx], ref_t, atol=1e-9), \
        "output cadence changed — regenerate the golden file deliberately"
    for name, ref_vals in ref.items():
        if name in ("group", "time"):
            continue
        ref_vals = np.asarray(ref_vals)
        if name.endswith(("_x", "_y", "_z")):
            vals = np.asarray(group[name[:-2]])[idx, "xyz".index(name[-1])]
        else:
            vals = np.asarray(group[name])[idx]
        atol = (atol_overrides or {}).get(name, 0.0)
        assert np.allclose(vals, ref_vals, rtol=rtol, atol=atol), \
            f"golden mismatch in '{name}': max |Δ| = " \
            f"{np.abs(vals - ref_vals).max():.6g}"


def test_golden_gps_1hr(xml_h5):
    """Equinoctial EOM reference (GPS orbit, 1 h)."""
    times, data = xml_h5
    # atol floors for quantities that oscillate through zero.
    _check_golden(times, data, GOLDEN_GPS, rtol=1e-7,
                  atol_overrides={"eccentricity": 1e-9, "inc": 1e-9})


def test_golden_leo_equatorial(leo_h5):
    """OblateEarth 6DOF EOM reference (equatorial LEO, one orbit)."""
    times, data = leo_h5
    _check_golden(times, data, GOLDEN_LEO, rtol=1e-7,
                  atol_overrides={"Latitude": 1e-9})
