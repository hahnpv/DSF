#ifndef SIGN_H
#define SIGN_H

//#pragma once

namespace dsf
{
	namespace util
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

#endif
