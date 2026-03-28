/**
 * @file gauss.h
 * @brief Random number generation utilities (Gaussian and uniform).
 *
 * Provides Box–Muller method Gaussian sampling and uniform distribution
 * functions for Monte Carlo and noise injection.
 */
#pragma once

#include <cmath>
#include <cstdlib>

namespace dsf
{
	namespace util
	{
	/**
	 * @brief Set random seed for reproducible Monte Carlo runs.
	 * @param seed Seed value for srand().
	 */
	void set_seed(unsigned int seed)
	{
		srand(seed);
	}

		/**
		 * @brief Generate a Gaussian-distributed random number.
		 *
		 * Uses the Box–Muller transform (polar form).
		 *
		 * @param mean  Distribution mean.
		 * @param stdev Distribution standard deviation.
		 * @return Random sample from N(mean, stdev²).
		 */
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

		/**
		 * @brief Generate a uniformly-distributed random number.
		 * @param min Lower bound.
		 * @param max Upper bound.
		 * @return Random sample from U[min, max].
		 */
		double getUniform(double min, double max) 
		{
			return min + (max-min) * ((double)rand()/RAND_MAX);
		}
	}
}
