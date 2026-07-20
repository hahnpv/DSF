/**
 * @file gauss.h
 * @brief Random number generation utilities (Gaussian and uniform).
 *
 * Provides Box–Muller method Gaussian sampling and uniform distribution
 * functions for Monte Carlo and noise injection.
 *
 * The engine is std::mt19937_64: its bit stream is specified by the C++
 * standard, so a given seed reproduces the same draw sequence on every
 * platform/compiler. The Box–Muller transform and 53-bit uniform mapping
 * live here (rather than std::normal_distribution, whose algorithm is
 * implementation-defined) to keep that reproducibility end to end.
 *
 * One global engine, no locking: draws happen outside the integration loop
 * (MC case setup, discrete events), never concurrently.
 */
#pragma once

#include <cmath>
#include <random>

namespace dsf
{
	namespace util
	{
	/// The shared Monte Carlo engine (function-local static: one instance
	/// process-wide across the DSF/model shared libraries).
	inline std::mt19937_64& mc_engine()
	{
		static std::mt19937_64 engine;
		return engine;
	}

	/**
	 * @brief Set random seed for reproducible Monte Carlo runs.
	 * @param seed Seed value for the mt19937_64 engine.
	 */
	inline void set_seed(unsigned int seed)
	{
		mc_engine().seed(seed);
	}

		/// 53-bit uniform draw in [0, 1) — the top bits of one engine word.
		inline double unit_uniform()
		{
			return (mc_engine()() >> 11) * (1.0 / 9007199254740992.0);  // / 2^53
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
		inline double get_gauss(double mean, double stdev)
		{
			double x1, x2, w;
			do
			{
				x1 = 2.0 * unit_uniform() - 1.0;
				x2 = 2.0 * unit_uniform() - 1.0;
				w  = x1*x1 + x2*x2;
			}
			while ( w >= 1.0 || w == 0.0 );

			return mean + x1 * sqrt( -2.0 * log(w) / w ) * stdev;
		};

		/**
		 * @brief Generate a uniformly-distributed random number.
		 * @param min Lower bound.
		 * @param max Upper bound.
		 * @return Random sample from [min, max).
		 */
		inline double getUniform(double min, double max)
		{
			return min + (max-min) * unit_uniform();
		}
	}
}
