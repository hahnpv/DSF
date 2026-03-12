"""Vehicle configuration utilities for JAX Monte Carlo.

Converts vehicle config dicts into JAX-compatible parameter arrays.
For MVP, configs are Python dicts. Phase 2 would add XML parsing.
"""
import jax.numpy as jnp


def make_state0(x, y, z, u, v, w, m):
    """Create an initial state vector.

    Args:
        x, y, z: ECI position [m].
        u, v, w: ECI velocity [m/s].
        m: total vehicle mass [kg].

    Returns:
        JAX array, shape (7,).
    """
    return jnp.array([x, y, z, u, v, w, m], dtype=jnp.float64)


def make_params(Cd, Sref, Isp, max_thrust, throttle=1.0, dry_mass=0.0):
    """Create a parameter dict from vehicle properties.

    Args:
        Cd: drag coefficient.
        Sref: reference area [m^2].
        Isp: specific impulse [s].
        max_thrust: maximum thrust [N].
        throttle: throttle setting [0..1], default 1.0.
        dry_mass: dry mass [kg], default 0.0.

    Returns:
        Dict of JAX scalars.
    """
    return {
        'Cd': jnp.float64(Cd),
        'Sref': jnp.float64(Sref),
        'Isp': jnp.float64(Isp),
        'max_thrust': jnp.float64(max_thrust),
        'throttle': jnp.float64(throttle),
        'dry_mass': jnp.float64(dry_mass),
    }


# --- Pre-built configs ---

def falcon9_stage1():
    """Falcon 9 Block 5 Stage 1 configuration (simplified).

    Based on sixdof/examples/falcon9/falcon9_debug.xml.
    Single-tank simplification: total propellant = fuel + ox.
    """
    # 9 × Merlin 1D engines
    n_engines = 9
    max_thrust_per = 845222.0  # N
    Isp = 295.0                # s (sea level)

    # Propellant: RP-1 + LOX
    fuel_mass = 111151.0       # kg RP-1
    ox_mass = 284549.0         # kg LOX
    total_prop = fuel_mass + ox_mass

    # Dry mass (structure + engines + payload stack)
    dry_mass_booster = 17700.0
    engine_dry = n_engines * 500.0
    # Stage 2 sits on top during Stage 1 burn
    stage2_mass = (32300.0 + 75200.0 + 2500.0 + 1500.0 + 15600.0)  # fuel+ox+dry+engine+payload

    total_dry = dry_mass_booster + engine_dry + stage2_mass
    total_mass = total_dry + total_prop

    # Initial state: Launch from equator, ECI
    R_earth = 6378137.0  # + 100m pad elevation
    state0 = make_state0(
        x=R_earth + 100.0, y=0.0, z=0.0,
        u=0.0, v=0.0, w=463.3,  # Earth rotation at equator
        m=total_mass
    )

    params = make_params(
        Cd=0.2,
        Sref=2.87,  # π * (1.83/2)^2 ≈ 2.63, XML uses 2.87
        Isp=Isp,
        max_thrust=n_engines * max_thrust_per,
        throttle=1.0,
        dry_mass=total_dry,
    )

    return state0, params
