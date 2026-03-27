# Entry Guidance Tuning — Lessons Learned

## Overview
Hard-won lessons from tuning the `EntryGuidance` controller for hypersonic lifting-body reentry
(Space Shuttle / X-37B class vehicles) through DSF's 6DOF simulation framework.

---

## 1. Initial Condition Alignment

### NED Velocity Must Match Heading
The `OblateEarth` EOM expects the velocity vector `<velocity>Vn, Ve, Vd</velocity>` in
**North-East-Down** components. If the vehicle's structural orientation (yaw ψ in `<orientation>`)
points at heading ψ, then:

```
Vn = V * cos(ψ)
Ve = V * sin(ψ)
Vd = V * sin(|γ|)   (positive = downward in NED)
```

**Critical bug**: Setting `<velocity>7600, 0, 157</velocity>` when heading is 56° East
creates a **56-degree sideslip at Mach 25**, destroying all vertical lift. The vehicle
enters the atmosphere sideways and dives uncontrollably.

### Vacuum Zone Bypass
Without a modeled RCS (Reaction Control System), a rigid body in vacuum above ~85 km maintains
fixed inertial attitude while the Earth curves away. By the time it reaches the atmosphere,
its body axes have rotated relative to the wind vector, creating massive sideslip.

**Fix**: Start the simulation at the **Aerodynamic Entry Interface** (~85 km) where control
surfaces can immediately maintain alignment, rather than at 120 km in vacuum.

---

## 2. SpaceplaneAero — Hypersonic Lift/Drag

### Newtonian Impact Theory
For blunt lifting bodies at α > 20° and M > 5:
```
CD = CD0 + k_bridge * sin²(α)     // k_bridge ≈ 2.6 for Shuttle
CL = k_bridge * sin(α) * cos(α)
```

At α = 40°: CL ≈ 0.84, CD ≈ 0.84, giving L/D ≈ 1.0 (matches STS data).

### Legacy Scaling Factor
The original `MissileAero` code applied a hardcoded `0.615` diameter scaling factor.
When migrating to `SpaceplaneAero` with a proper `Sref` attribute, this factor was
left in, drastically underestimating forces and causing 70+ minute reentry times.
**Remove all legacy scaling when using direct Sref.**

### Body Flap
Hypersonic trim at α=40° requires a body flap:
- Deflection: ~12° above Mach 5 and α > 20°
- Drag penalty: `CD += delta_bf * 0.01`  
- Pitch moment: `Cm -= 0.05` (nose-down trim offset)

---

## 3. Energy Management — Analytic Glide Tracker

### The Skip Problem
Skip-bounce trajectories occur when the guidance demands more vertical lift than the
atmosphere can absorb. The vehicle overshoots into space, re-enters, overshoots again.

**Root cause**: The phugoid damper commanded unbounded vertical lift correction forces.
When the vehicle dove at -150 m/s, the damper demanded 3,000,000 N of vertical lift,
which could only be achieved at near-zero bank angle. At the bottom of the dive, this
massive lift hurled the vehicle back to 100+ km altitude.

### Solution: Kinetic Energy Polynomial Tracker with Lift Ceiling
Replace the static sink-rate target with a V²-proportional range reference:
```cpp
double R_ref = (V * V) * 0.12;       // V=7500 → R_ref = 6750 km
double r_err = range - R_ref;         // Positive = falling short
double h_dot_nom = -V / 150.0;       // Natural sink rate
double h_dot_target = h_dot_nom + 1e-4 * r_err;
h_dot_target = clamp(h_dot_target, -60.0, 10.0);  // Never >60 m/s dive
```

**Critical**: Cap the delta-lift correction to prevent skip-rebound:
```cpp
double delta_lift = -15000.0 * h_dot_err;
delta_lift = clamp(delta_lift, -50000, 150000);  // 1.5 G ceiling
required_vert_lift += delta_lift;
required_vert_lift = max(required_vert_lift, mass * 0.1 * g);  // 10% floor
```

### Bank Angle Limits
Max bank should never exceed ~78° (cos(78°) ≈ 0.20) to always retain at least
20% of vertical lift. At 87°+ bank, vertical lift ≈ 0, causing freefall.

---

## 4. Cross-Range Steering (Bank Reversals)

### Dynamic Azimuth Funnel
To limit bank reversals to < 10 (STS nominal: 3-4), use a velocity-dependent deadband:
```cpp
double dynamic_thresh = base_thresh + max(0, (V - 1000) / 6500) * 80.0;
// At M=25: ±100° tolerance. At M=2: ±20° tolerance.
```

**Key tuning parameters**:
- `bank_reversal_threshold`: 15-20° baseline (collapses at low Mach)
- Funnel multiplier: 80° provides 3-4 reversals for Shuttle-class trajectories
- Wider funnel = fewer reversals but potentially larger cross-range at landing

---

## 5. Slew Rate Limiter (RK4 Correction)
The bank actuator rate limit must account for RK4's 4 sub-steps per physics step:
```cpp
double max_d_bank = (max_bank_rate * dt) / 4.0;
```
Without the `/4.0`, the actuator moves 4× faster than intended, causing unrealistic
150 deg/s bank rate transients.

---

## 6. Vehicle-Specific Parameters

### Space Shuttle
| Parameter | Value |
|-----------|-------|
| Mass | 80,000 kg |
| Sref | 249.9 m² |
| cbar | 12.06 m |
| b | 23.79 m |
| Entry speed | 7,600 m/s (M ≈ 22.3) |
| Entry alt | 85-120 km |
| Target L/D | 1.0 (hypersonic) |
| Flight time | ~35-45 min |
| Range | ~6,500-7,500 km |

### X-37B
| Parameter | Value |
|-----------|-------|
| Mass | 3,500 kg (dry) |
| Sref | 10.0 m² |
| cbar | 4.55 m |
| b | 4.55 m |
| Entry speed | 7,600 m/s (M ≈ 22.3) |
| Target L/D | ~1.5-2.0 (higher than Shuttle) |

---

## 7. Debugging Checklist

1. **Vehicle not decelerating?** → Check Sref, legacy scaling factors, Newtonian bridge factor
2. **Excessive skipping?** → Reduce phugoid gain, add delta-lift ceiling, ensure bank ≤ 78°
3. **Too many bank reversals?** → Widen the dynamic funnel multiplier
4. **Diving into ground?** → Check NED velocity alignment with heading angle
5. **Flight time too long?** → Increase drag (Newtonian bridge factor, body flap)
6. **Actuators too fast?** → Verify `/4.0` RK4 correction in slew limiter
7. **Vehicle tumbling after 200s?** → Vacuum zone + no RCS → start at 85 km instead of 120 km
