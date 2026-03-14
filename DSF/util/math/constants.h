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
			const double C_DEG = 3.14159/180.; ///< Degrees-to-radians conversion factor.
			const double RAD   = 57.2958;      ///< Radians-to-degrees conversion factor.
			const double PI    = 3.14159;       ///< π (low precision — consider M_PI).
		}
	}
}