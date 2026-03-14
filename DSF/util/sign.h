/**
 * @file sign.h
 * @brief Sign function utility.
 */
#pragma once

namespace dsf
{
	namespace util
	{
		/// Returns +1 if x >= 0, -1 otherwise.
		inline int sign(double x)
		{
			if (x >= 0)
				return 1;
			else
				return -1;
		}
	}
}
