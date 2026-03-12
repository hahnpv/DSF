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

    // --- Sub-step loop: advance by exactly dt_nominal ---
    double t_covered = 0.0;
    while (t_covered < dt_nominal - 1e-14)
    {
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
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[1][i] = *d->xd[i];

        // Stage 3
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b31 * d->xdd[0][i] + b32 * d->xdd[1][i]);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[2][i] = *d->xd[i];

        // Stage 4
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b41 * d->xdd[0][i] + b42 * d->xdd[1][i]
                                        + b43 * d->xdd[2][i]);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[3][i] = *d->xd[i];

        // Stage 5
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b51 * d->xdd[0][i] + b52 * d->xdd[1][i]
                                        + b53 * d->xdd[2][i] + b54 * d->xdd[3][i]);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[4][i] = *d->xd[i];

        // Stage 6
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (b61 * d->xdd[0][i] + b62 * d->xdd[1][i]
                                        + b63 * d->xdd[2][i] + b64 * d->xdd[3][i]
                                        + b65 * d->xdd[4][i]);
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[5][i] = *d->xd[i];

        // 5th-order solution
        for (int i = 0; i < n; i++)
            *d->x[i] = d->x0[i] + h * (c1 * d->xdd[0][i] + c3 * d->xdd[2][i]
                                        + c4 * d->xdd[3][i] + c5 * d->xdd[4][i]
                                        + c6 * d->xdd[5][i]);

        // k7 (FSAL) for error estimate
        dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
        for (int i = 0; i < n; i++) d->xdd[6][i] = *d->xd[i];

        // Error estimation
        double err_max = 0.0;
        for (int i = 0; i < n; i++)
        {
            double err_i = h * std::fabs(e1 * d->xdd[0][i] + e3 * d->xdd[2][i]
                                        + e4 * d->xdd[3][i] + e5 * d->xdd[4][i]
                                        + e6 * d->xdd[5][i] + e7 * d->xdd[6][i]);
            double scale = atol_ + rtol_ * std::fabs(*d->x[i]);
            err_max = std::max(err_max, err_i / scale);
        }

        if (err_max <= 1.0)
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
            for (int i = 0; i < n; i++)
                *d->x[i] = d->x0[i];

            double factor = 0.9 * std::pow(err_max, -0.25);
            factor = std::max(factor, 0.1);
            dt_adapt_ = std::max(h * factor, dt_min_);

            // Re-evaluate derivatives at restored state
            dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);
            for (int i = 0; i < n; i++)
                d->xdd[0][i] = *d->xd[i];
        }
    }

    // --- Advance clock by nominal dt (2 ticks, same as RK4) ---
    clock->increment();
    clock->increment();
    clock->set(true);
}

} // namespace sim
} // namespace dsf
