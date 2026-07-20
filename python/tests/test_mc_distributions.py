"""
test_mc_distributions.py
------------------------
Statistical V&V of the Monte Carlo random draw functions in util/gauss.h
(set_seed / get_gauss / getUniform), exposed through the dsf_core bindings.
These are the exact functions the MC dispatcher (sim/monte_carlo.h) uses to
draw dispersions, so this suite validates that gaussian/uniform dispersions
are statistically correct: moments, full-CDF agreement (Kolmogorov-Smirnov),
tail coverage (what the extreme-draw report keys on), bounds, draw
granularity (guards against a small RAND_MAX quantizing draws), seed
reproducibility/independence, and population-level agreement with the JAX
Monte Carlo mirror (dsf.jax uses jax.random.normal for the same dispersions).

Draws are generated in a subprocess (same pattern as test_dsf_bindings.py:
the C extension stays out of the Qt-loaded pytest process) and saved as .npz;
the parent process does the statistics with numpy/scipy only.

All draws use fixed seeds, so every assertion is deterministic — tolerances
are set with wide margin for the sample sizes used, not tuned to the seed.
"""
import os
import sys
import subprocess
import textwrap

import numpy as np
import pytest
from scipy import stats

PYTHON     = sys.executable
DSF_REPO   = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PYTHON_SRC = os.path.join(DSF_REPO, "python")

N       = 200_000          # draws per distribution
G_MEAN  = 10.0             # non-trivial mean/sigma so scale bugs can't hide
G_SIGMA = 3.0
U_MIN   = -2.0
U_MAX   = 5.0
SEED    = 1234
SEED2   = 987654           # for independence checks
P_MIN   = 1e-3             # KS acceptance: deterministic with fixed seed,
                           # margin checked at authoring time (p >> 0.01)

_DRIVER = f"""\
import sys, os
sys.path.insert(0, {PYTHON_SRC!r})
sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
import numpy as np
import dsf

out = sys.argv[1]

dsf.set_seed({SEED})
gauss = np.array(dsf.gauss_samples({G_MEAN}, {G_SIGMA}, {N}))
uniform = np.array(dsf.uniform_samples({U_MIN}, {U_MAX}, {N}))

# same seed again -> replay both streams (reproducibility)
dsf.set_seed({SEED})
gauss_replay = np.array(dsf.gauss_samples({G_MEAN}, {G_SIGMA}, {N}))
uniform_replay = np.array(dsf.uniform_samples({U_MIN}, {U_MAX}, {N}))

# different seed -> independent stream
dsf.set_seed({SEED2})
gauss_other = np.array(dsf.gauss_samples({G_MEAN}, {G_SIGMA}, {N}))

# scalar path must be the identical code path as the batch helper
dsf.set_seed({SEED})
scalar = np.array([dsf.get_gauss({G_MEAN}, {G_SIGMA}) for _ in range(1000)])

np.savez(out, gauss=gauss, uniform=uniform,
         gauss_replay=gauss_replay, uniform_replay=uniform_replay,
         gauss_other=gauss_other, scalar=scalar)
"""


@pytest.fixture(scope="module")
def draws(tmp_path_factory):
    """Generate all sample sets once in a dsf subprocess; load with numpy."""
    out = str(tmp_path_factory.mktemp("mc_draws") / "draws.npz")
    env = os.environ.copy()
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:  # dsf_core.so needs conda's libhdf5 (see test_dsf_bindings)
        env["LD_LIBRARY_PATH"] = (os.path.join(conda_prefix, "lib") + ":"
                                  + env.get("LD_LIBRARY_PATH", ""))
    r = subprocess.run([PYTHON, "-c", textwrap.dedent(_DRIVER), out],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        pytest.skip(f"dsf_core RNG bindings unavailable:\n{r.stderr[-2000:]}")
    return np.load(out)


# ---------------------------------------------------------------------------
# Gaussian (polar Box-Muller over mt19937_64)
# ---------------------------------------------------------------------------

class TestGaussian:
    def test_finite(self, draws):
        g = draws["gauss"]
        assert np.all(np.isfinite(g))

    def test_moments(self, draws):
        g = draws["gauss"]
        se_mean = G_SIGMA / np.sqrt(N)
        assert abs(g.mean() - G_MEAN) < 5 * se_mean
        # sd of the sample std for a normal is ~ sigma/sqrt(2N)
        assert abs(g.std(ddof=1) - G_SIGMA) < 5 * G_SIGMA / np.sqrt(2 * N)
        # skewness se ~ sqrt(6/N), excess-kurtosis se ~ sqrt(24/N)
        assert abs(stats.skew(g)) < 5 * np.sqrt(6.0 / N)
        assert abs(stats.kurtosis(g)) < 5 * np.sqrt(24.0 / N)

    def test_ks_against_analytic_cdf(self, draws):
        res = stats.kstest(draws["gauss"], stats.norm(G_MEAN, G_SIGMA).cdf)
        assert res.pvalue > P_MIN, f"KS p={res.pvalue:.2e}, D={res.statistic:.4f}"

    def test_tail_coverage(self, draws):
        """Fractions beyond k-sigma vs erfc — extreme draws must not be
        clipped or inflated (the MC extreme-draw report keys on these)."""
        z = np.abs(draws["gauss"] - G_MEAN) / G_SIGMA
        for k in (1.0, 2.0, 3.0):
            expected = 2.0 * stats.norm.sf(k)
            observed = np.mean(z > k)
            se = np.sqrt(expected * (1 - expected) / N)
            assert abs(observed - expected) < 6 * se, (
                f"P(|z|>{k}): observed {observed:.5f}, expected {expected:.5f}")

    def test_symmetry(self, draws):
        g = draws["gauss"]
        above = np.mean(g > G_MEAN)
        assert abs(above - 0.5) < 6 * np.sqrt(0.25 / N)


# ---------------------------------------------------------------------------
# Uniform
# ---------------------------------------------------------------------------

class TestUniform:
    def test_bounds(self, draws):
        u = draws["uniform"]
        assert u.min() >= U_MIN and u.max() <= U_MAX
        # endpoints should be approached: expected gap ~ range/N
        rng = U_MAX - U_MIN
        assert u.min() - U_MIN < 100 * rng / N
        assert U_MAX - u.max() < 100 * rng / N

    def test_moments(self, draws):
        u = draws["uniform"]
        rng = U_MAX - U_MIN
        se_mean = rng / np.sqrt(12 * N)
        assert abs(u.mean() - (U_MIN + U_MAX) / 2) < 5 * se_mean
        var_expected = rng**2 / 12.0
        # sd of sample variance for uniform ~ var*sqrt(4/(5N)) (kurt=-1.2)
        assert abs(u.var(ddof=1) - var_expected) < 5 * var_expected * np.sqrt(4.0 / (5 * N))

    def test_ks_against_analytic_cdf(self, draws):
        res = stats.kstest(draws["uniform"],
                           stats.uniform(loc=U_MIN, scale=U_MAX - U_MIN).cdf)
        assert res.pvalue > P_MIN, f"KS p={res.pvalue:.2e}, D={res.statistic:.4f}"

    def test_granularity(self, draws):
        """The unit-uniform mapping must not quantize draws (53-bit via
        mt19937_64; collisions among 200k draws are essentially impossible).
        A coarse generator, e.g. a 15-bit RAND_MAX, would fail this."""
        u = draws["uniform"]
        assert len(np.unique(u)) > N - 1000


# ---------------------------------------------------------------------------
# Seeding: reproducibility and stream independence
# ---------------------------------------------------------------------------

class TestSeeding:
    def test_same_seed_replays_exactly(self, draws):
        assert np.array_equal(draws["gauss"], draws["gauss_replay"])
        assert np.array_equal(draws["uniform"], draws["uniform_replay"])

    def test_scalar_and_batch_paths_identical(self, draws):
        assert np.array_equal(draws["scalar"], draws["gauss"][:1000])

    def test_different_seeds_uncorrelated(self, draws):
        a, b = draws["gauss"], draws["gauss_other"]
        assert not np.array_equal(a, b)
        r = np.corrcoef(a, b)[0, 1]
        assert abs(r) < 6 / np.sqrt(N)

    def test_no_serial_correlation(self, draws):
        """Lag-1..3 autocorrelation of the stream ~ 0 (Box-Muller consumes
        engine words in pairs; serial structure would surface here)."""
        g = draws["gauss"] - G_MEAN
        for lag in (1, 2, 3):
            r = np.corrcoef(g[:-lag], g[lag:])[0, 1]
            assert abs(r) < 6 / np.sqrt(N), f"lag-{lag} autocorr {r:.4f}"


# ---------------------------------------------------------------------------
# Cross-validation against the JAX Monte Carlo mirror
# ---------------------------------------------------------------------------

class TestJaxCrossValidation:
    def test_gauss_population_matches_jax(self, draws):
        """dsf.jax disperses with jax.random.normal; the C++ dispatcher with
        get_gauss. Same sigma must give statistically identical populations
        (two-sample KS), or MC results differ by backend."""
        jax = pytest.importorskip("jax")
        key = jax.random.PRNGKey(0)
        jx = G_MEAN + G_SIGMA * np.asarray(
            jax.random.normal(key, shape=(50_000,)), dtype=np.float64)
        res = stats.ks_2samp(draws["gauss"][:50_000], jx)
        assert res.pvalue > P_MIN, f"2-sample KS p={res.pvalue:.2e}"
