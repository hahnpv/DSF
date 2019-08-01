#pragma once

#include <cmath>
#include <stdlib.h>
namespace dsf
{
	namespace util
	{
		template<class T>
		void set_seed(T t)
		{
			// set seed to t 

			// linux
			//	srand( (unsigned)time(NULL) );
		}

		double get_gauss(double mean, double stdev) 
		{
			double x1, x2, w, y1, y2;
			do 
			{
				x1 = 2.0 * ((double)rand()/RAND_MAX) - 1.0;
				x2 = 2.0 * ((double)rand()/RAND_MAX) - 1.0;
				w  = pow( x1, 2) + pow( x2, 2);
			} 
			while ( w >= 1.0 || w == 0.0 );

			double trans = sqrt( -2.0 * log(w) / w );
			y1 = x1 * trans; 
			y2 = x2 * trans;
			return mean + y1*stdev;	
		};


		double getUniform(double min, double max) 
		{
			return min + (max-min) * ((double)rand()/RAND_MAX);
		}
	};
};
