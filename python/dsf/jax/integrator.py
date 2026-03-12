"""Fixed-step RK4 integrator with JAX vmap support.

Provides single-case propagation via jax.lax.fori_loop and batched
propagation via jax.vmap for Monte Carlo execution.
"""
import jax
import jax.numpy as jnp
from functools import partial


def rk4_step(deriv_fn, state, params, dt):
    """Perform one RK4 integration step.

    Args:
        deriv_fn: function(state, params) → d_state/dt, shape (n,).
        state: current state vector, shape (n,).
        params: parameter dict (passed through to deriv_fn).
        dt: timestep [s].

    Returns:
        Updated state vector, shape (n,).
    """
    k1 = deriv_fn(state, params)
    k2 = deriv_fn(state + dt / 2.0 * k1, params)
    k3 = deriv_fn(state + dt / 2.0 * k2, params)
    k4 = deriv_fn(state + dt * k3, params)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def propagate(deriv_fn, state0, params, dt, n_steps):
    """Propagate a trajectory for n_steps using RK4.

    Uses jax.lax.fori_loop for JIT-compatible looping.

    Args:
        deriv_fn: function(state, params) → d_state/dt.
        state0: initial state vector, shape (n,).
        params: parameter dict.
        dt: timestep [s].
        n_steps: number of integration steps.

    Returns:
        Final state vector, shape (n,).
    """
    def body_fn(i, state):
        return rk4_step(deriv_fn, state, params, dt)

    return jax.lax.fori_loop(0, n_steps, body_fn, state0)


def propagate_with_history(deriv_fn, state0, params, dt, n_steps, save_every=1):
    """Propagate and record the trajectory at regular intervals.

    Uses jax.lax.scan for efficient history storage.

    Args:
        deriv_fn: function(state, params) → d_state/dt.
        state0: initial state vector, shape (n,).
        params: parameter dict.
        dt: timestep [s].
        n_steps: number of integration steps.
        save_every: record state every N steps (default: every step).

    Returns:
        Tuple of (final_state, history):
            final_state: shape (n,)
            history: shape (n_steps // save_every, n)
    """
    def scan_body(state, _):
        # Advance save_every steps
        def inner_step(i, s):
            return rk4_step(deriv_fn, s, params, dt)
        new_state = jax.lax.fori_loop(0, save_every, inner_step, state)
        return new_state, new_state

    n_saves = n_steps // save_every
    final_state, history = jax.lax.scan(scan_body, state0, None, length=n_saves)
    return final_state, history


def propagate_batch(deriv_fn, states0, params_batch, dt, n_steps, save_every=1):
    """Propagate a batch of trajectories in parallel via vmap.

    Args:
        deriv_fn: function(state, params) → d_state/dt.
        states0: initial states, shape (n_cases, n_state).
        params_batch: dict of arrays, each with leading dim n_cases.
        dt: timestep [s] (scalar, shared across all cases).
        n_steps: number of steps (scalar).
        save_every: record interval.

    Returns:
        Tuple of (final_states, histories):
            final_states: shape (n_cases, n_state)
            histories: shape (n_cases, n_saves, n_state)
    """
    # vmap over the leading axis of states and each param array
    vmapped = jax.vmap(
        lambda s0, p: propagate_with_history(deriv_fn, s0, p, dt, n_steps, save_every),
        in_axes=(0, 0)
    )
    return vmapped(states0, params_batch)
