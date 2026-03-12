/**
 * @file integrator_base.h
 * @brief Abstract base class for numerical integrators.
 *
 * Defines the strategy interface for pluggable integration methods.
 * Concrete implementations: IntegratorRK4, IntegratorRK45, IntegratorVerlet.
 *
 * ## XML Selection
 * @code{.xml}
 * <sim dt="0.01" tmax="600" integrator="RK45" atol="1e-8" rtol="1e-6" />
 * @endcode
 */
#pragma once

namespace dsf
{
namespace sim
{

class Block;
class Clock;

/// Tag for integrand type — used by symplectic integrators to distinguish
/// position-like states (q) from momentum-like states (p).
/// Non-symplectic integrators ignore this tag.
enum class IntegrandType
{
    GENERIC,    ///< Default — integrated normally by all methods
    POSITION,   ///< Position-like (q): dq/dt = v (function of momentum)
    MOMENTUM    ///< Momentum-like (p): dp/dt = F (function of position)
};

/**
 * @class IntegratorBase
 * @brief Abstract interface for numerical integration strategies.
 */
class IntegratorBase
{
public:
    virtual ~IntegratorBase() = default;

    /// Advance all registered states by one step.
    /// Calls Block::update() on root's children as needed for derivative evaluation.
    virtual void propagate(Block* root) = 0;

    /// Number of intermediate stages (derivative evaluations) per step.
    /// Used by TIntDict to size workspace and by Clock for tick accounting.
    virtual int stages() const = 0;

    /// Whether this integrator uses adaptive step control.
    virtual bool is_adaptive() const { return false; }

    /// Clock reference (set by Sim::load)
    Clock* clock = nullptr;
};

} // namespace sim
} // namespace dsf
