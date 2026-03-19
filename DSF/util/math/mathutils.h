/**
 * @file mathutils.h
 * @brief Common math utilities for clamping and angle wrapping.
 */
#pragma once

#include <cmath>
#include <algorithm>

namespace dsf
{
namespace util
{

/**
 * @brief Clamps a value between a lower and upper bound.
 * @param v The value to clamp.
 * @param lo The lower bound.
 * @param hi The upper bound.
 * @return The clamped value.
 */
inline double clamp(double v, double lo, double hi)
{
    return std::max(lo, std::min(hi, v));
}

/**
 * @brief Alias for clamp().
 */
inline double clamp_val(double v, double lo, double hi)
{
    return std::max(lo, std::min(hi, v));
}

/**
 * @brief Wraps an angle to the interval [-π, π].
 * @param angle The angle in radians.
 * @return The wrapped angle in radians.
 */
inline double wrap_pi(double angle)
{
    if (std::isnan(angle) || std::isinf(angle)) return angle;
    angle = std::fmod(angle + M_PI, 2.0 * M_PI);
    if (angle < 0) angle += 2.0 * M_PI;
    return angle - M_PI;
}

/**
 * @brief Rate limits a command.
 * @param cmd The new commanded value.
 * @param prev The previous value.
 * @param max_rate The maximum rate of change (units per second).
 * @param dt The time step [s].
 * @return The rate-limited command.
 */
inline double rate_limit(double cmd, double prev, double max_rate, double dt)
{
    double max_delta = max_rate * dt;
    double delta = cmd - prev;
    if (delta > max_delta)  return prev + max_delta;
    if (delta < -max_delta) return prev - max_delta;
    return cmd;
}

} // namespace util
} // namespace dsf
