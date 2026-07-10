/**
 * @file test_integrators.cpp
 * @brief Numerical-validation harness for the DSF integration FRAMEWORK.
 *
 * DSF is a framework; physics models live in the sibling `sixdof` project.
 * These tests therefore validate the framework's numerical machinery
 * (RK4 / RK45 / Verlet + the clock) against canonical ODE problems with known
 * closed-form solutions, using tiny self-contained test "models" defined here.
 * No sixdof dependency.
 *
 * Canonical problems:
 *   - Exponential decay  y' = -λy            → convergence order (RK4 ~4th)
 *   - Simple harmonic osc  x'=v, v'=-ω²x     → energy conservation, Verlet vs RK4
 *   - Two-body / Kepler  r'' = -μ r/|r|³     → orbit closure, energy + ang.mom.
 *   - Non-autonomous  y' = cos(t)            → clock advances stage times (RK4)
 *
 * Registered by CMake as the `cpp_integrator_tests` ctest.
 */
#include "sim/block.h"
#include "sim/clock.h"
#include "sim/TClassDict.h"
#include "sim/TIntDict.h"
#include "sim/integratorRK4.h"
#include "sim/integrator_rk45.h"
#include "sim/integrator_verlet.h"
#include "util/math/vec3.h"

#include <iostream>
#include <cmath>
#include <string>
#include <functional>

using namespace dsf::sim;
using dsf::util::Vec3;

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg)                                                        \
    do {                                                                        \
        if (!(cond)) {                                                          \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n";     \
            tests_failed++;                                                     \
        } else { tests_passed++; }                                             \
    } while (0)

#define CHECK_NEAR(val, expected, tol, msg)                                     \
    CHECK(std::fabs((val) - (expected)) < (tol),                                \
          std::string(msg) + " got=" + std::to_string(val) +                    \
          " expected=" + std::to_string(expected))

// ---------------------------------------------------------------------------
// Test models — trivial Blocks that register state/derivative pairs (exactly
// like a real DSF model, cf. examples/bouncy) and compute an RHS in update().
// ---------------------------------------------------------------------------

class ExpDecay : public Block {
public:
    double y = 1.0, dy = 0.0, lambda = 1.0;
    void init() override {
        TClassIntegrandDict<Block>::Instance()->add(
            TClass<ExpDecay, Block>::Instance(), y, dy);
    }
    void update() override { dy = -lambda * y; }
};

class SHO : public Block {
public:
    double x = 1.0, dx = 0.0, v = 0.0, dv = 0.0, omega = 2.0;
    bool symplectic_tags = false;   // tag states for Verlet when true
    void init() override {
        auto* d = TClassIntegrandDict<Block>::Instance();
        auto* owner = TClass<SHO, Block>::Instance();
        d->add(owner, x, dx, symplectic_tags ? IntegrandType::POSITION : IntegrandType::GENERIC);
        d->add(owner, v, dv, symplectic_tags ? IntegrandType::MOMENTUM : IntegrandType::GENERIC);
    }
    void update() override { dx = v; dv = -omega * omega * x; }
    double energy() const { return 0.5 * v * v + 0.5 * omega * omega * x * x; }
};

class TwoBody : public Block {
public:
    Vec3 r{1, 0, 0}, dr{0, 0, 0}, v{0, 1, 0}, dv{0, 0, 0};
    double mu = 1.0;
    bool symplectic_tags = false;
    void init() override {
        auto* d = TClassIntegrandDict<Block>::Instance();
        auto* owner = TClass<TwoBody, Block>::Instance();
        d->add(owner, r, dr, symplectic_tags ? IntegrandType::POSITION : IntegrandType::GENERIC);
        d->add(owner, v, dv, symplectic_tags ? IntegrandType::MOMENTUM : IntegrandType::GENERIC);
    }
    void update() override {
        dr = v;
        double R = r.mag();
        double a = -mu / (R * R * R);
        dv = Vec3(r.x * a, r.y * a, r.z * a);
    }
    double energy() { return 0.5 * v.dot(v) - mu / r.mag(); }
    Vec3   angmom() { return r.cross(v); }
};

// y' = cos(t): non-autonomous. Uses t() → exercises clock stage-time advance.
class CosForcing : public Block {
public:
    double y = 0.0, dy = 0.0;
    void init() override {
        TClassIntegrandDict<Block>::Instance()->add(
            TClass<CosForcing, Block>::Instance(), y, dy);
    }
    void update() override { dy = std::cos(t()); }
};

// ---------------------------------------------------------------------------
// Driver: register the model as a child of a root Block and step the given
// integrator from t=0 to tmax. No Sim/Output required.
// ---------------------------------------------------------------------------

template <class Model>
void integrate(Model& model, IntegratorBase& integ, double dt, double tmax)
{
    TClassIntegrandDict<Block>::Instance()->clear();
    Clock clock(dt, tmax);
    integ.clock = &clock;

    Block root;
    root.addChild(&model);
    model.ClockRef(&clock);
    model.init();

    long guard = 0;
    const long MAX = 100000000;
    while (clock.t() < tmax - dt * 0.5 && ++guard < MAX)
        integ.propagate(&root);
}

// ---------------------------------------------------------------------------
// Exponential decay — accuracy + convergence order
// ---------------------------------------------------------------------------

void test_exp_decay_accuracy()
{
    IntegratorRK4 rk4;
    ExpDecay m; m.y = 1.0; m.lambda = 1.0;
    integrate(m, rk4, 0.01, 2.0);
    CHECK_NEAR(m.y, std::exp(-2.0), 1e-6, "RK4 exp decay y(2)");

    IntegratorRK45 rk45(1e-10, 1e-10);
    rk45.set_step_bounds(1e-6, 0.1);
    ExpDecay m2; m2.y = 1.0; m2.lambda = 1.0;
    integrate(m2, rk45, 0.01, 2.0);
    CHECK_NEAR(m2.y, std::exp(-2.0), 1e-6, "RK45 exp decay y(2)");
}

void test_rk4_convergence_order()
{
    // Global error of a 4th-order method scales as dt^4, so halving dt should
    // cut the error by ~16x. This is the signature that confirms RK4 is really
    // 4th order (and that stages are staged/weighted correctly).
    auto err = [](double dt) {
        IntegratorRK4 rk4;
        ExpDecay m; m.y = 1.0; m.lambda = 1.0;
        integrate(m, rk4, dt, 1.0);
        return std::fabs(m.y - std::exp(-1.0));
    };
    double e1 = err(0.02);
    double e2 = err(0.01);
    double ratio = e1 / e2;
    CHECK(ratio > 12.0 && ratio < 20.0,
          std::string("RK4 error ratio (dt halved) ~16, got ") + std::to_string(ratio));
}

// ---------------------------------------------------------------------------
// Simple harmonic oscillator — accuracy + symplectic energy behavior
// ---------------------------------------------------------------------------

void test_sho_rk4_one_period()
{
    // x0=1, v0=0, ω=2 → x(t)=cos(2t); after one period T=π, x returns to 1.
    IntegratorRK4 rk4;
    SHO m; m.x = 1.0; m.v = 0.0; m.omega = 2.0;
    double T = M_PI;  // 2*pi/omega
    integrate(m, rk4, 0.001, T);
    CHECK_NEAR(m.x, 1.0, 1e-3, "RK4 SHO x after one period");
    CHECK_NEAR(m.v, 0.0, 1e-2, "RK4 SHO v after one period");
}

void test_sho_verlet_energy_conservation()
{
    // The defining symplectic property: Verlet's energy error stays BOUNDED for
    // all time, while RK4 (non-symplectic) leaks energy SECULARLY — its error
    // grows roughly linearly with the integration horizon. So we check the
    // qualitative behavior (regime-independent), not a single-horizon magnitude.
    const double dt = 0.05, omega = 2.0;
    const double E0 = 0.5 * omega * omega;  // x0=1, v0=0
    auto rel_energy_err = [&](IntegratorBase& integ, bool tags, double tmax) {
        SHO m; m.x = 1.0; m.v = 0.0; m.omega = omega; m.symplectic_tags = tags;
        integrate(m, integ, dt, tmax);
        return std::fabs(m.energy() - E0) / E0;
    };

    IntegratorVerlet v1, v2;
    double verlet_short = rel_energy_err(v1, true, 200.0);
    double verlet_long  = rel_energy_err(v2, true, 1600.0);   // 8x horizon

    IntegratorRK4 r1, r2;
    double rk4_short = rel_energy_err(r1, false, 200.0);
    double rk4_long  = rel_energy_err(r2, false, 1600.0);     // 8x horizon

    // Verlet: bounded at both horizons (does not grow with time).
    CHECK(verlet_long < 0.02, std::string("Verlet energy bounded over long run, rel err ")
          + std::to_string(verlet_long));
    CHECK(verlet_long < 3.0 * verlet_short + 1e-9,
          std::string("Verlet energy error does not grow secularly (short=")
          + std::to_string(verlet_short) + " long=" + std::to_string(verlet_long) + ")");

    // RK4: energy error grows with the horizon (secular drift) — the thing the
    // symplectic method avoids.
    CHECK(rk4_long > 2.0 * rk4_short,
          std::string("RK4 energy drifts secularly with time (short=")
          + std::to_string(rk4_short) + " long=" + std::to_string(rk4_long) + ")");
}

// ---------------------------------------------------------------------------
// Two-body / Kepler — orbit closure + conserved quantities
// ---------------------------------------------------------------------------

void test_twobody_circular_orbit()
{
    // Circular orbit: μ=1, a=1, r0=(1,0,0), v0=(0,1,0). Period T=2π.
    // Specific energy E = -μ/2a = -0.5; |h| = |r×v| = 1.
    IntegratorRK4 rk4;
    TwoBody m;
    m.r = Vec3(1, 0, 0); m.v = Vec3(0, 1, 0); m.mu = 1.0;
    double E0 = m.energy();
    double h0 = m.angmom().mag();
    CHECK_NEAR(E0, -0.5, 1e-12, "two-body initial energy");
    CHECK_NEAR(h0, 1.0, 1e-12, "two-body initial ang.mom.");

    integrate(m, rk4, 0.001, 2.0 * M_PI);

    // Orbit closes: returns near r0.
    Vec3 dr = m.r - Vec3(1, 0, 0);
    CHECK(dr.mag() < 5e-3, std::string("two-body orbit closure |Δr|=") + std::to_string(dr.mag()));
    // Conserved quantities hold to integrator tolerance.
    CHECK_NEAR(m.energy(), E0, 1e-5, "two-body energy conserved");
    CHECK_NEAR(m.angmom().mag(), h0, 1e-6, "two-body ang.mom. conserved");
}

// ---------------------------------------------------------------------------
// Non-autonomous — confirms the clock advances through RK4 stage times
// ---------------------------------------------------------------------------

void test_nonautonomous_rk4()
{
    // y' = cos(t), y(0)=0 → y(t)=sin(t). If stage times were frozen at the
    // start of the step, this would be visibly wrong; RK4 advances the clock at
    // half/full step, so it is accurate.
    IntegratorRK4 rk4;
    CosForcing m;
    integrate(m, rk4, 0.001, M_PI / 2.0);
    CHECK_NEAR(m.y, 1.0, 1e-4, "RK4 non-autonomous y(pi/2)=sin(pi/2)");
}

int main()
{
    std::cout << "=== DSF integrator validation (framework, no sixdof) ===\n";

    test_exp_decay_accuracy();
    test_rk4_convergence_order();
    test_sho_rk4_one_period();
    test_sho_verlet_energy_conservation();
    test_twobody_circular_orbit();
    test_nonautonomous_rk4();

    std::cout << "\n=== Results: " << tests_passed << " passed, "
              << tests_failed << " failed ===\n";
    return tests_failed > 0 ? 1 : 0;
}
