/**
 * @file integrator_verlet.h
 * @brief Störmer-Verlet (leapfrog) symplectic integrator.
 *
 * Preserves the symplectic structure of Hamiltonian systems, giving bounded
 * energy error over arbitrarily long integration times. Ideal for orbital
 * mechanics and n-body problems.
 *
 * Requires integrands to be registered with IntegrandType::POSITION or
 * IntegrandType::MOMENTUM tags. GENERIC integrands are integrated as
 * MOMENTUM (force-driven) by default.
 *
 * ## XML Configuration
 * @code{.xml}
 * <sim dt="10.0" tmax="86400" integrator="Verlet" />
 * @endcode
 */
#pragma once

#include "integrator_base.h"

namespace dsf
{
namespace sim
{

class IntegratorVerlet : public IntegratorBase
{
public:
    IntegratorVerlet() = default;

    void propagate(Block* root) override;
    int stages() const override { return 2; }
};

} // namespace sim
} // namespace dsf
