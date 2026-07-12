#include "integrator_rk45.h"
#include "block.h"
#include "clock.h"
#include "TIntDict.h"
#include "../util/TFunctor.h"
#include <cmath>
#include <algorithm>
#include <iostream>

namespace dsf
{
namespace sim
{

// Dormand-Prince Butcher tableau coefficients
const double IntegratorRK45::a2 = 1.0/5.0;
const double IntegratorRK45::a3 = 3.0/10.0;
const double IntegratorRK45::a4 = 4.0/5.0;
const double IntegratorRK45::a5 = 8.0/9.0;
const double IntegratorRK45::a6 = 1.0;

const double IntegratorRK45::b21 = 1.0/5.0;
const double IntegratorRK45::b31 = 3.0/40.0;
const double IntegratorRK45::b32 = 9.0/40.0;
const double IntegratorRK45::b41 = 44.0/45.0;
const double IntegratorRK45::b42 = -56.0/15.0;
const double IntegratorRK45::b43 = 32.0/9.0;
const double IntegratorRK45::b51 = 19372.0/6561.0;
const double IntegratorRK45::b52 = -25360.0/2187.0;
const double IntegratorRK45::b53 = 64448.0/6561.0;
const double IntegratorRK45::b54 = -212.0/729.0;
const double IntegratorRK45::b61 = 9017.0/3168.0;
const double IntegratorRK45::b62 = -355.0/33.0;
const double IntegratorRK45::b63 = 46732.0/5247.0;
const double IntegratorRK45::b64 = 49.0/176.0;
const double IntegratorRK45::b65 = -5103.0/18656.0;

// 5th-order weights
const double IntegratorRK45::c1 = 35.0/384.0;
const double IntegratorRK45::c3 = 500.0/1113.0;
const double IntegratorRK45::c4 = 125.0/192.0;
const double IntegratorRK45::c5 = -2187.0/6784.0;
const double IntegratorRK45::c6 = 11.0/84.0;

// Error coefficients: e_i = c_i - c_hat_i (5th order minus 4th order)
const double IntegratorRK45::e1 = 71.0/57600.0;
const double IntegratorRK45::e3 = -71.0/16695.0;
const double IntegratorRK45::e4 = 71.0/1920.0;
const double IntegratorRK45::e5 = -17253.0/339200.0;
const double IntegratorRK45::e6 = 22.0/525.0;
const double IntegratorRK45::e7 = -1.0/40.0;

IntegratorRK45::IntegratorRK45(double atol, double rtol)
    : atol_(atol), rtol_(rtol), dt_adapt_(0), dt_min_(1e-12), dt_max_(1.0),
      total_steps_(0), rejected_steps_(0)
{
}

void IntegratorRK45::set_step_bounds(double dt_min, double dt_max)
{
    dt_min_ = dt_min;
    dt_max_ = dt_max;
}


/**
 * RK45 adaptive integrator — sub-steps within the Clock's nominal dt.
 *
 * Strategy:
 *   The Clock defines the "macro" step dt_nominal. Each call to propagate()
 *   advances the simulation by exactly dt_nominal (one macro step).
 *   Internally, RK45 may take multiple adaptive sub-steps to cover dt_nominal,
 *   growing/shrinking h based on error estimates.
 *
 * This preserves:
 *   - Output sample timing (controlled by Clock::Sample)
 *   - FCS scheduling (blocks check clock time for phase transitions)
 *   - Backward compatibility (if tolerances are loose, takes a single step)
 */
// Classic fixed-step RK4 over one interval h starting at stage time t0 (seconds
// past the macro step's tick time). Mirrors IntegratorRK4 but runs as an in-line
// sub-step of the adaptive loop, so it does NOT tick the clock — stage times are
// carried via Clock::set_stage_offset (the enclosing propagate() advances the
// ticks once for the whole macro step). On entry d->x holds the sub-step start
// state and d->xdd[0] holds k1 = f(t0, start); on exit d->x is advanced by h and
// d->xdd[0] is re-evaluated at the new state/time.
void IntegratorRK45::rk4_fallback_step(Block* root, int n, double t0, double h)
{
    auto* d = TClassIntegrandDict<Block>::Instance();

    // x0 = current state; k1 already in xdd[0].
    for (int i = 0; i < n; i++)
        d->x0[i] = *d->x[i];

    // k2 = f(t0 + h/2, x0 + h/2 k1)
    for (int i = 0; i < n; i++)
        *d->x[i] = d->x0[i] + 0.5 * h * d->xdd[0][i];
    clock->set_stage_offset(t0 + 0.5 * h);
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
    for (int i = 0; i < n; i++) d->xdd[1][i] = *d->xd[i];

    // k3 = f(t0 + h/2, x0 + h/2 k2)
    for (int i = 0; i < n; i++)
        *d->x[i] = d->x0[i] + 0.5 * h * d->xdd[1][i];
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
    for (int i = 0; i < n; i++) d->xdd[2][i] = *d->xd[i];

    // k4 = f(t0 + h, x0 + h k3)
    for (int i = 0; i < n; i++)
        *d->x[i] = d->x0[i] + h * d->xdd[2][i];
    clock->set_stage_offset(t0 + h);
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
    for (int i = 0; i < n; i++) d->xdd[3][i] = *d->xd[i];

    // x = x0 + h/6 (k1 + 2k2 + 2k3 + k4)
    for (int i = 0; i < n; i++)
        *d->x[i] = d->x0[i] + (h / 6.0) * (d->xdd[0][i] + 2.0 * d->xdd[1][i]
                                            + 2.0 * d->xdd[2][i] + d->xdd[3][i]);

    // Re-prime k1 at the new state/time (FSAL continuity for the next macro step).
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
    for (int i = 0; i < n; i++) d->xdd[0][i] = *d->xd[i];
}

void IntegratorRK45::propagate(Block* root)
{
    auto* d = TClassIntegrandDict<Block>::Instance();
    int n = static_cast<int>(d->x.size());
    if (n == 0) return;

    // Ensure workspace sized for 7 stages (6 + FSAL)
    if (d->xdd.size() < 7)
        d->resize_stages(7);

    double dt_nominal = clock->dt();

    // Initialize adaptive sub-step size on first call
    if (dt_adapt_ <= 0)
        dt_adapt_ = dt_nominal;

    // --- Initial derivative evaluation (at current state) ---
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
    clock->set(false);

    // Save initial state
    for (int i = 0; i < n; i++)
    {
        d->x0[i] = *d->x[i];
        d->xdd[0][i] = *d->xd[i];  // k1
    }

    // Stage times: the tick clock (2 ticks per dt) cannot represent
    // Dormand-Prince stage fractions or adaptive sub-step boundaries, so each
    // stage evaluation carries its true time (t_covered + c_i*h, seconds past
    // the macro tick time) via Clock::set_stage_offset — time-dependent models
    // reading t() in update() see correct stage times. The offset is cleared
    // before the macro-step tick advance below, so events, reports, and FCS
    // scheduling still see pure tick time. [R2 / A11]

    // --- Sub-step loop: advance by exactly dt_nominal ---
    //
    // STIFF / NON-SMOOTH FALLBACK. An embedded error controller cannot cross a
    // stiff mode or a *discontinuity* (e.g. Coulomb-friction sign flip at v=0 on
    // a parked/rolling gear, or a hard contact transition): the local-error test
    // never passes and h collapses toward dt_min, stalling the run. A fixed-step
    // method has no such test — it simply steps over the non-smooth region, which
    // is exactly why the RK4 decks fly the same scenarios. So when the adaptive
    // step is clearly struggling THIS macro step (too many rejections or a runaway
    // sub-step count), we finish the macro step with a single fixed RK4 step over
    // the remaining interval (h <= dt_nominal, the RK4 decks' proven step) and
    // move on. Smooth phases never trip this and keep full adaptive efficiency.
    const int    STIFF_REJECT_LIMIT  = 6;    // rejections in one macro step -> stiff
    const int    STIFF_SUBSTEP_LIMIT = 64;   // sub-steps in one macro step -> collapsing
    int rejects_this_macro = 0;

    double t_covered = 0.0;
    int substep_guard = 0;
    const int MAX_SUBSTEPS = 100000;	// backstop against a non-converging step
    while (t_covered < dt_nominal - 1e-14)
    {
        // Non-smooth/stiff detected: hand the rest of this macro step to fixed RK4.
        if (rejects_this_macro >= STIFF_REJECT_LIMIT ||
            substep_guard       >= STIFF_SUBSTEP_LIMIT)
        {
            rk4_fallback_step(root, n, t_covered, dt_nominal - t_covered);
            t_covered = dt_nominal;
            stiff_fallbacks_++;
            if (!stiff_warned_)
            {
                std::cerr << "IntegratorRK45: adaptive step stalled (stiff or "
                          << "non-smooth dynamics, e.g. gear friction/contact); "
                          << "falling back to fixed RK4 for affected steps"
                          << std::endl;
                stiff_warned_ = true;
            }
            // Optimistic reset: retry full adaptive stepping next macro step.
            dt_adapt_ = dt_nominal;
            break;
        }

        if (++substep_guard > MAX_SUBSTEPS)
        {
            std::cerr << "IntegratorRK45: exceeded " << MAX_SUBSTEPS
                      << " sub-steps in one macro step (stiff or non-finite "
                      << "dynamics); ending simulation" << std::endl;
            clock->end();
            break;
        }

        double t_remaining = dt_nominal - t_covered;
        double h = std::min(dt_adapt_, t_remaining);

        // Clamp h to exactly finish the macro step
        if (h > t_remaining * 0.999)
            h = t_remaining;

        // Save sub-step start state
        for (int i = 0; i < n; i++)
            d->x0[i] = *d->x[i];

        // Try a Dormand-Prince step of size h
        total_steps_++;

        // --- Inline stages (using saved k1 in xdd[0]) ---

        // Stage 2
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * b21 * d->xdd[0][i];
        clock->set_stage_offset(t_covered + a2 * h);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[1][i] = *d->xd[i];

        // Stage 3
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b31 * d->xdd[0][i] + b32 * d->xdd[1][i]);
        clock->set_stage_offset(t_covered + a3 * h);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[2][i] = *d->xd[i];

        // Stage 4
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b41 * d->xdd[0][i] + b42 * d->xdd[1][i]
                                        + b43 * d->xdd[2][i]);
        clock->set_stage_offset(t_covered + a4 * h);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[3][i] = *d->xd[i];

        // Stage 5
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b51 * d->xdd[0][i] + b52 * d->xdd[1][i]
                                        + b53 * d->xdd[2][i] + b54 * d->xdd[3][i]);
        clock->set_stage_offset(t_covered + a5 * h);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[4][i] = *d->xd[i];

        // Stage 6
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b61 * d->xdd[0][i] + b62 * d->xdd[1][i]
                                        + b63 * d->xdd[2][i] + b64 * d->xdd[3][i]
                                        + b65 * d->xdd[4][i]);
        clock->set_stage_offset(t_covered + a6 * h);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[5][i] = *d->xd[i];

        // 5th-order solution
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (c1 * d->xdd[0][i] + c3 * d->xdd[2][i]
                                        + c4 * d->xdd[3][i] + c5 * d->xdd[4][i]
                                        + c6 * d->xdd[5][i]);

        // k7 (FSAL) for error estimate — at the end-of-sub-step time
        clock->set_stage_offset(t_covered + h);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[6][i] = *d->xd[i];

        // Error estimation. A NaN/Inf derivative must NOT be accepted: since
        // std::max(x, NaN) returns x, a naive max would leave err_max finite and
        // silently accept a non-finite step, propagating NaN through the state.
        double err_max = 0.0;
        bool nonfinite = false;
        for (int i = 0; i < n; i++)
        {
            double err_i = h * std::fabs(e1 * d->xdd[0][i] + e3 * d->xdd[2][i]
                                        + e4 * d->xdd[3][i] + e5 * d->xdd[4][i]
                                        + e6 * d->xdd[5][i] + e7 * d->xdd[6][i]);
            if (!std::isfinite(err_i) || !std::isfinite(*d->x[i]))
            {
                nonfinite = true;
                break;
            }
            double scale = atol_ + rtol_ * std::fabs(*d->x[i]);
            err_max = std::max(err_max, err_i / scale);
        }

        if (!nonfinite && err_max <= 1.0)
        {
            // Accept sub-step
            t_covered += h;

            // FSAL: k7 of this step becomes k1 of next sub-step
            for (int i = 0; i < n; i++)
                d->xdd[0][i] = d->xdd[6][i];

            // Grow dt_adapt for next sub-step
            double factor = (err_max > 1e-10) ? 0.9 * std::pow(err_max, -0.2) : 5.0;
            factor = std::min(factor, 5.0);
            factor = std::max(factor, 0.2);
            dt_adapt_ = std::min(h * factor, dt_max_);
            dt_adapt_ = std::max(dt_adapt_, dt_min_);
        }
        else
        {
            // Reject — restore state, shrink h
            rejected_steps_++;
            rejects_this_macro++;
            for (int i = 0; i < n; i++)
                *d->x[i] = d->x0[i];

            // Re-evaluate derivatives at the restored state and its time (also
            // primes k1 for a possible RK4 fallback on the next loop iteration).
            clock->set_stage_offset(t_covered);
            dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
            for (int i = 0; i < n; i++)
                d->xdd[0][i] = *d->xd[i];

            // A non-finite derivative that shrinking cannot fix is unrecoverable;
            // the fixed-RK4 fallback can't help either, so stop rather than spin.
            if (nonfinite && h <= dt_min_ * (1.0 + 1e-12))
            {
                std::cerr << "IntegratorRK45: non-finite derivatives at minimum "
                          << "step size; ending simulation" << std::endl;
                clock->end();
                break;
            }

            // At the minimum step and still rejecting (finite): this is stiff /
            // non-smooth, not an accuracy problem shrinking can solve. Force the
            // fixed-RK4 fallback on the next loop iteration instead of ending.
            if (h <= dt_min_ * (1.0 + 1e-12))
            {
                rejects_this_macro = STIFF_REJECT_LIMIT;
                continue;
            }

            double factor = nonfinite ? 0.1 : std::max(0.9 * std::pow(err_max, -0.25), 0.1);
            dt_adapt_ = std::max(h * factor, dt_min_);
        }
    }

    // --- Advance clock by nominal dt (2 ticks, same as RK4) ---
    // Stage offset back to zero first: from here on (constrain/update, events,
    // reports) time is the macro boundary, pure tick arithmetic.
    clock->set_stage_offset(0.0);
    clock->increment();
    clock->increment();

    // Post-integration constraint hook (see Block::constrain): invoked once
    // per macro step after the final accepted sub-step committed the states,
    // with the clock at end-of-step time. The update() that follows refreshes
    // derived outputs and derivatives at the constrained state (also
    // re-priming the FSAL/initial derivative evaluated at the top of the next
    // propagate() call).
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::constrain);
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);

    clock->set(true);
}

} // namespace sim
} // namespace dsf
