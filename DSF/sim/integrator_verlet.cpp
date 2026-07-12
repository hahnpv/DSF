#include "integrator_verlet.h"
#include "block.h"
#include "clock.h"
#include "TIntDict.h"
#include "../util/TFunctor.h"

namespace dsf
{
namespace sim
{

/**
 * Störmer-Verlet (velocity Verlet) symplectic integration.
 *
 * For each step:
 *   1. Half-kick:   p_{n+½} = p_n + (dt/2) * dp/dt(q_n)
 *   2. Drift:       q_{n+1} = q_n + dt * dq/dt(p_{n+½})
 *   3. Evaluate derivatives at new position
 *   4. Half-kick:   p_{n+1} = p_{n+½} + (dt/2) * dp/dt(q_{n+1})
 *
 * Integrands tagged POSITION are q-like (updated in drift step).
 * Integrands tagged MOMENTUM are p-like (updated in kick steps).
 * Integrands tagged GENERIC are treated as MOMENTUM (force-driven).
 */
void IntegratorVerlet::propagate(Block* root)
{
    auto* d = TClassIntegrandDict<Block>::Instance();
    int n = static_cast<int>(d->x.size());
    if (n == 0) return;

    double dt = clock->dt();
    double half_dt = dt * 0.5;

    // Initial derivative evaluation (forces at current state)
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);

    clock->set(false);

    // Step 1: Half-kick — advance momentum by dt/2
    for (int i = 0; i < n; i++)
    {
        if (d->types[i] == IntegrandType::POSITION)
            continue;  // skip position states in kick step

        // Momentum/generic: p += (dt/2) * dp/dt
        *d->x[i] += half_dt * (*d->xd[i]);
    }

    // Step 2: Drift — advance position by full dt using the half-stepped momentum
    // First re-evaluate derivatives so position derivatives see updated momentum
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);

    for (int i = 0; i < n; i++)
    {
        if (d->types[i] != IntegrandType::POSITION)
            continue;  // skip momentum states in drift step

        // Position: q += dt * dq/dt(p_{n+½})
        *d->x[i] += dt * (*d->xd[i]);
    }

    // Step 3: Re-evaluate derivatives at the new position (forces at q_{n+1},
    // which velocity-Verlet defines at t+dt). This used to run after a single
    // tick — i.e. at t+dt/2 — which mistimed time-dependent forces; the stage
    // offset carries the correct end-of-step time. [R2]
    clock->set_stage_offset(dt);
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);

    // Step 4: Half-kick — advance momentum by another dt/2
    for (int i = 0; i < n; i++)
    {
        if (d->types[i] == IntegrandType::POSITION)
            continue;

        *d->x[i] += half_dt * (*d->xd[i]);
    }

    // Commit the macro ticks together (offset back to zero first — end-of-step
    // time is pure tick time for events/reports/constrain).
    clock->set_stage_offset(0.0);
    clock->increment();
    clock->increment();

    // Post-integration constraint hook (see Block::constrain): invoked once
    // per step after the final half-kick committed the momentum states, with
    // the clock at end-of-step time. No extra update() here — the symplectic
    // path keeps its force-evaluation count; derived outputs refresh at the
    // next step's first update().
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::constrain);

    clock->set(true);
}

} // namespace sim
} // namespace dsf
