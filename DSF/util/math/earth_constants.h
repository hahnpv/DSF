/**
 * @file earth_constants.h
 * @brief Central WGS84 Earth constants for the DSF/sixdof framework.
 *
 * All subsystems requiring Earth-related physical constants should include
 * this header rather than defining local values.
 */
#pragma once

namespace dsf
{
    namespace util
    {
        namespace earth
        {
            /// WGS84 gravitational parameter [m³/s²]
            constexpr double MU_EARTH     = 3.986004418e14;

            /// WGS84 semi-major axis (equatorial radius) [m]
            constexpr double RE_EARTH     = 6378137.0;

            /// WGS84 first zonal harmonic (oblateness) [-]
            constexpr double J2_EARTH     = 0.001081874;

            /// Standard gravity (ISO 80000-3) [m/s²]
            constexpr double G0           = 9.80665;

            /// WGS84 Earth rotation rate [rad/s]
            constexpr double OMEGA_EARTH  = 7.2921159e-5;

            /// WGS84 flattening [-]
            constexpr double F_EARTH      = 1.0 / 298.257223563;

            /// WGS84 semi-minor axis (polar radius) [m]
            constexpr double RP_EARTH     = RE_EARTH * (1.0 - F_EARTH);
        }
    }
}
