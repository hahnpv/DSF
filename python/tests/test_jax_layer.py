"""
Tests for the JAX layer (H3): config, RK4 integration loop, Monte Carlo
dispatcher. Self-contained — the dsf.jax modules take any pure
deriv_fn(state, params), so no sixdof models are needed.
"""
import numpy as np
import pytest

jax = pytest.importorskip("jax")
jnp = pytest.importorskip("jax.numpy")

import dsf.jax  # noqa: E402  (side effect under test: enables x64)
from dsf.jax.config import make_state0, make_params, falcon9_stage1  # noqa: E402
from dsf.jax.integrator import (  # noqa: E402
    rk4_step, propagate, propagate_with_history, propagate_batch)
from dsf.jax.monte_carlo import (  # noqa: E402
    disperse_state, disperse_params, run_monte_carlo)


# ── config: float64 (A23) ───────────────────────────────────────────────────

def test_x64_enabled_at_import():
    assert jax.config.jax_enable_x64 is True


def test_make_state0_is_float64():
    s = make_state0(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    assert s.shape == (7,)
    assert s.dtype == jnp.float64


def test_make_params_is_float64():
    p = make_params(Cd=0.3, Sref=10.0, Isp=300.0, max_thrust=1e6)
    assert all(jnp.asarray(v).dtype == jnp.float64 for v in p.values())


def test_falcon9_stage1_prebuilt():
    state0, params = falcon9_stage1()
    assert state0.shape == (7,)
    assert "Isp" in params


# ── integrator: accuracy against closed form ────────────────────────────────

def _decay(state, params):
    """y' = -k y  →  y(t) = y0 exp(-k t)."""
    return -params["k"] * state


def test_propagate_exponential_decay():
    y = propagate(_decay, jnp.array([1.0]), {"k": jnp.array(1.0)},
                  dt=0.01, n_steps=100)
    assert float(y[0]) == pytest.approx(np.exp(-1.0), rel=1e-9)


def test_rk4_convergence_order():
    """Halving dt must cut the global error ~16x (4th order)."""
    def err(dt, n):
        y = propagate(_decay, jnp.array([1.0]), {"k": jnp.array(1.0)},
                      dt=dt, n_steps=n)
        return abs(float(y[0]) - np.exp(-1.0))
    ratio = err(0.02, 50) / err(0.01, 100)
    assert 12.0 < ratio < 20.0


def test_rk4_step_matches_propagate_single():
    s0 = jnp.array([1.0, 2.0])
    p = {"k": jnp.array(0.5)}
    one = rk4_step(_decay, s0, p, 0.1)
    via_loop = propagate(_decay, s0, p, dt=0.1, n_steps=1)
    assert np.allclose(np.asarray(one), np.asarray(via_loop))


def test_propagate_with_history_shapes_and_final():
    final, hist = propagate_with_history(
        _decay, jnp.array([1.0]), {"k": jnp.array(1.0)},
        dt=0.01, n_steps=100, save_every=10)
    assert hist.shape == (10, 1)
    assert np.allclose(np.asarray(hist[-1]), np.asarray(final))
    # history is the decaying trajectory, strictly decreasing
    h = np.asarray(hist[:, 0])
    assert (np.diff(h) < 0).all()


def test_propagate_batch_vmap():
    states0 = jnp.array([[1.0], [2.0], [4.0]])
    params = {"k": jnp.array([1.0, 1.0, 1.0])}
    finals, hists = propagate_batch(_decay, states0, params,
                                    dt=0.01, n_steps=100, save_every=100)
    assert finals.shape == (3, 1)
    assert hists.shape == (3, 1, 1)
    # linear ODE: scaling the IC scales the solution
    f = np.asarray(finals[:, 0])
    assert f[1] == pytest.approx(2 * f[0], rel=1e-12)
    assert f[2] == pytest.approx(4 * f[0], rel=1e-12)


# ── Monte Carlo dispatcher ──────────────────────────────────────────────────

def test_disperse_state_shape_and_stats():
    key = jax.random.PRNGKey(0)
    out = disperse_state(jnp.array([10.0, 0.0]), jnp.array([1.0, 0.0]),
                         n_cases=2000, key=key)
    assert out.shape == (2000, 2)
    a = np.asarray(out)
    assert a[:, 0].mean() == pytest.approx(10.0, abs=0.1)   # ~5 sigma/sqrt(n)
    assert a[:, 0].std() == pytest.approx(1.0, abs=0.1)
    assert (a[:, 1] == 0.0).all()                            # sigma=0 → exact


def test_disperse_params_broadcast_without_sigma():
    key = jax.random.PRNGKey(1)
    out = disperse_params({"k": 2.0, "c": 5.0}, {"k": 0.1}, n_cases=8, key=key)
    assert out["k"].shape == (8,) and out["c"].shape == (8,)
    assert (np.asarray(out["c"]) == 5.0).all()
    assert np.asarray(out["k"]).std() > 0.0


def test_run_monte_carlo_shapes_and_determinism():
    kwargs = dict(
        deriv_fn=_decay,
        nominal_state=jnp.array([1.0]),
        state_sigmas=jnp.array([0.1]),
        nominal_params={"k": 1.0},
        param_sigmas={"k": 0.05},
        dt=0.01, n_steps=50, n_cases=16, save_every=10,
    )
    r1 = run_monte_carlo(seed=42, **kwargs)
    assert r1["final_states"].shape == (16, 1)
    assert r1["histories"].shape == (16, 5, 1)
    assert r1["states0"].shape == (16, 1)

    r2 = run_monte_carlo(seed=42, **kwargs)
    assert np.array_equal(np.asarray(r1["final_states"]),
                          np.asarray(r2["final_states"]))

    r3 = run_monte_carlo(seed=43, **kwargs)
    assert not np.array_equal(np.asarray(r1["final_states"]),
                              np.asarray(r3["final_states"]))


def test_run_monte_carlo_zero_sigma_collapses_to_nominal():
    r = run_monte_carlo(
        deriv_fn=_decay,
        nominal_state=jnp.array([1.0]),
        state_sigmas=jnp.array([0.0]),
        nominal_params={"k": 1.0},
        param_sigmas={},
        dt=0.01, n_steps=100, n_cases=4, seed=0)
    f = np.asarray(r["final_states"][:, 0])
    assert np.allclose(f, np.exp(-1.0), rtol=1e-9)
    assert np.allclose(f, f[0])
