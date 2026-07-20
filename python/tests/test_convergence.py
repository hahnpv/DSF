"""
Full-stack code verification: Richardson self-convergence of the assembled
deck -> sixdof models -> RK4 -> HDF5 chain.

test/test_integrators.cpp verifies observed order-of-accuracy on toy ODEs in
isolation; this verifies the ASSEMBLED executive shows the same 4th-order
signature on a real deck (leo_equatorial.xml, OblateEarth 6-DOF EOM under
WGS84 J2). No analytic reference is required: three runs at 4dt, 2dt, dt give

    p = log2( max|r_4dt - r_2dt| / max|r_2dt - r_dt| )  ~= 4

The whole-deck version has diagnostic breadth the toy tests cannot: a table
kink, an unlocalized discontinuity, stale stage state in a model, or a
mis-staged executive collapses p toward 1 even while single-dt point checks
still look plausible.

Calibration (2026-07): p = 4.01 for the (16,8,4) triplet and 4.00 for
(8,4,2); the (16,8,4) differences (2.3e-3 m vs 1.4e-4 m) sit far above the
float64 output floor, so the coarse triplet is used for speed.

Sims run in subprocesses via the conftest pattern; requires sixdof.
"""
import os
import re

import numpy as np
import h5py

from tests.conftest import FIXTURES_DIR, require_sixdof, run_sim

LEO_XML = os.path.join(FIXTURES_DIR, "leo_equatorial.xml")

# tmax and the output cadence are exact multiples of every dt, so all three
# runs sample the trajectory on the identical time grid (the tick clock makes
# those times exact — no interpolation enters the comparison).
TMAX = 640
FILE_S = 64
DTS = (16, 8, 4)  # coarse, medium, fine


def _deck(tmp_path, dt):
    txt = open(LEO_XML).read()
    txt = re.sub(r'\bdt="[^"]*"', f'dt="{dt}"', txt, count=1)
    txt = re.sub(r'\btmax="[^"]*"', f'tmax="{TMAX}"', txt, count=1)
    txt = re.sub(r'\bfile="[^"]*"', f'file="{FILE_S}"', txt, count=1)
    p = tmp_path / f"leo_dt{dt}.xml"
    p.write_text(txt)
    return str(p)


def _position(h5_path):
    with h5py.File(h5_path, "r") as f:
        t = np.array(f["Time"])
        r = np.stack([np.array(f[f"XYZ_ECI_{c}"]) for c in "xyz"], axis=1)
    return t, r


def test_full_deck_rk4_observed_order(tmp_path):
    require_sixdof()
    sols = []
    for dt in DTS:
        d = tmp_path / f"run_dt{dt}"
        d.mkdir()
        sols.append(_position(run_sim(_deck(tmp_path, dt), str(d))))

    (tc, rc), (tm, rm), (tf, rf) = sols
    assert np.allclose(tc, tm, atol=1e-9) and np.allclose(tm, tf, atol=1e-9), \
        "output time grids must align across dt for a direct state comparison"

    d1 = np.abs(rc - rm).max()   # |r_4dt - r_2dt|
    d2 = np.abs(rm - rf).max()   # |r_2dt - r_dt|
    assert d2 > 1e-8, \
        f"solution differences ({d2:.3e} m) too near roundoff to measure order"

    p = np.log2(d1 / d2)
    assert 3.4 < p < 4.6, \
        f"observed order p={p:.2f} (d1={d1:.3e} m, d2={d2:.3e} m) — " \
        "the assembled deck is not converging at RK4's formal order; " \
        "suspect a non-smooth model term, unlocalized event, or stage bug"
