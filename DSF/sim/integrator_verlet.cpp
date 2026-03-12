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

    clock->increment();

    // Step 3: Re-evaluate derivatives at new position (forces at q_{n+1})
    dsf::util::TFunctor<Block>(root->getChildren(), &Block::update);

    // Step 4: Half-kick — advance momentum by another dt/2
    for (int i = 0; i < n; i++)
    {
        if (d->types[i] == IntegrandType::POSITION)
            continue;

        *d->x[i] += half_dt * (*d->xd[i]);
    }

    clock->increment();
    clock->set(true);
}

} // namespace sim
} // namespace dsf
