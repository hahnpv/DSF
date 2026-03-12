/**
 * @file integrator_rk45.h
 * @brief Dormand-Prince RK45 adaptive-step integrator.
 *
 * Provides 5th-order accurate integration with embedded 4th-order error
 * estimation for automatic step size control.
 *
 * ## XML Configuration
 * @code{.xml}
 * <sim dt="0.01" tmax="600" integrator="RK45" atol="1e-8" rtol="1e-6" />
 * @endcode
 */
#pragma once

#include "integrator_base.h"

namespace dsf
{
namespace sim
{

class IntegratorRK45 : public IntegratorBase
{
public:
    /// @param atol Absolute error tolerance per state variable
    /// @param rtol Relative error tolerance per state variable
    IntegratorRK45(double atol = 1e-8, double rtol = 1e-6);

    void propagate(Block* root) override;
    int stages() const override { return 6; }
    bool is_adaptive() const override { return true; }

    /// Set min/max step bounds
    void set_step_bounds(double dt_min, double dt_max);

    /// Get the current adaptive dt (may differ from Clock::dt)
    double current_dt() const { return dt_adapt_; }

    /// Step statistics
    int total_steps() const { return total_steps_; }
    int rejected_steps() const { return rejected_steps_; }

private:
    double atol_;
    double rtol_;
    double dt_adapt_;           ///< Current adaptive step size
    double dt_min_;             ///< Minimum allowed step
    double dt_max_;             ///< Maximum allowed step
    int total_steps_;
    int rejected_steps_;

    /// Dormand-Prince coefficients
    static const double a2, a3, a4, a5, a6;
    static const double b21;
    static const double b31, b32;
    static const double b41, b42, b43;
    static const double b51, b52, b53, b54;
    static const double b61, b62, b63, b64, b65;
    static const double c1, c3, c4, c5, c6;           // 5th order weights
    static const double e1, e3, e4, e5, e6, e7;       // error = y5 - y4
};

} // namespace sim
} // namespace dsf
