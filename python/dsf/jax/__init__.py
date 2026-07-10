"""JAX-accelerated simulation framework for DSF.

Provides the integration loop, Monte Carlo dispatcher, and config
utilities. Uses physics models from sixdof.py.jax.
"""

# Enable 64-bit precision before any JAX arrays are created. The config/state
# builders request jnp.float64, but without this JAX silently downcasts to
# float32 (~0.5 m epsilon at ECI magnitudes), quietly corrupting orbital
# propagation. This must run at import time, ahead of any jax.numpy use.
try:
    import jax
    jax.config.update("jax_enable_x64", True)
except ImportError:
    # JAX is an optional dependency; the pure-Python submodules still import.
    pass
