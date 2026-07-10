/**
 * @file constants.h
 * @brief Common mathematical constants.
 */
#pragma once

namespace dsf
{
	namespace util
	{
		namespace math
		{
			const double PI    = 3.14159265358979323846; ///< π (full double precision).
			const double C_DEG = PI / 180.0;  ///< Degrees-to-radians conversion factor.
			const double RAD   = 180.0 / PI;  ///< Radians-to-degrees conversion factor.
		}
	}
}