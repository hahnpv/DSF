"""Monte Carlo dispersion and batch execution — JAX implementation.

Generates dispersed initial conditions and parameters using JAX PRNG,
then runs all cases in parallel via vmap.
"""
import jax
import jax.numpy as jnp
from .integrator import propagate_batch, propagate_with_history


def disperse_state(nominal_state, sigmas, n_cases, key):
    """Generate dispersed initial state vectors.

    Each element of the state is perturbed by Gaussian noise
    with standard deviation given by sigmas.

    Args:
        nominal_state: nominal initial state, shape (n_state,).
        sigmas: 1-sigma dispersions for each state element, shape (n_state,).
        n_cases: number of Monte Carlo cases.
        key: JAX PRNG key.

    Returns:
        Dispersed initial states, shape (n_cases, n_state).
    """
    noise = jax.random.normal(key, shape=(n_cases, nominal_state.shape[0]))
    return nominal_state[None, :] + sigmas[None, :] * noise


def disperse_params(nominal_params, param_sigmas, n_cases, key):
    """Generate dispersed parameter dicts.

    Each parameter is independently perturbed by Gaussian noise.

    Args:
        nominal_params: dict of nominal scalar parameter values.
        param_sigmas: dict of 1-sigma dispersions (same keys as nominal_params).
            Keys not present in param_sigmas are broadcast without dispersion.
        n_cases: number of Monte Carlo cases.
        key: JAX PRNG key.

    Returns:
        Dict of dispersed parameter arrays, each with shape (n_cases,).
    """
    dispersed = {}
    subkeys = jax.random.split(key, len(nominal_params))
    for i, (name, nominal_val) in enumerate(nominal_params.items()):
        nominal_val = jnp.asarray(nominal_val, dtype=jnp.float64)
        if name in param_sigmas and param_sigmas[name] != 0.0:
            sigma = jnp.asarray(param_sigmas[name], dtype=jnp.float64)
            noise = jax.random.normal(subkeys[i], shape=(n_cases,))
            dispersed[name] = nominal_val + sigma * noise
        else:
            # Broadcast scalar to all cases
            dispersed[name] = jnp.broadcast_to(nominal_val, (n_cases,))
    return dispersed


def run_monte_carlo(deriv_fn, nominal_state, state_sigmas,
                    nominal_params, param_sigmas,
                    dt, n_steps, n_cases, seed=0, save_every=1):
    """Run a full Monte Carlo batch.

    End-to-end: disperse → propagate → return all trajectories.

    Args:
        deriv_fn: function(state, params) → d_state/dt.
        nominal_state: nominal initial state, shape (n_state,).
        state_sigmas: 1-sigma dispersions for state, shape (n_state,).
        nominal_params: dict of nominal parameter scalars.
        param_sigmas: dict of parameter 1-sigma dispersions.
        dt: timestep [s].
        n_steps: number of integration steps.
        n_cases: number of Monte Carlo cases.
        seed: PRNG seed (int).
        save_every: record trajectory every N steps.

    Returns:
        Dict with:
            'final_states': shape (n_cases, n_state)
            'histories': shape (n_cases, n_saves, n_state)
            'states0': shape (n_cases, n_state) — the dispersed ICs
            'params': dispersed parameter dict
    """
    key = jax.random.PRNGKey(seed)
    key_state, key_params = jax.random.split(key)

    states0 = disperse_state(nominal_state, state_sigmas, n_cases, key_state)
    params_batch = disperse_params(nominal_params, param_sigmas, n_cases, key_params)

    final_states, histories = propagate_batch(
        deriv_fn, states0, params_batch, dt, n_steps, save_every)

    return {
        'final_states': final_states,
        'histories': histories,
        'states0': states0,
        'params': params_batch,
    }
