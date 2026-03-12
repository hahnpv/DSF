#pragma once

#include "integrator_base.h"

namespace dsf
{
namespace sim
{

/**
 * @class IntegratorRK4
 * @brief Classic 4th-order Runge-Kutta integrator.
 *
 * Four-stage fixed-step method. This is the default integrator and provides
 * backward compatibility with the original DSF integration behavior.
 */
class IntegratorRK4 : public IntegratorBase
{
public:
    IntegratorRK4() = default;

    void propagate(Block* root) override;
    int stages() const override { return 4; }

private:
    void rk4(int pass);
};

// Backward compatibility alias
using Integrator = IntegratorRK4;

} // namespace sim
} // namespace dsf