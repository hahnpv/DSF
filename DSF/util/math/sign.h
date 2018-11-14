#pragma once

namespace dsf
{
	namespace util
	{
		namespace math
		{
			/// Returns the sign of x.
			int sign(double x) 
			{
				if (x >= 0)
					return 1;
				else
					return -1;
			}
		}
	}
}