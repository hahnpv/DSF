#pragma once

#include "output.h"
#include <vector>

namespace dsf
{
	namespace sim 
	{
		class Clock;
		class Integrator;
		class Block;

		class Sim {
		public:
			void run();
			void load(Block * simulation, double dt, double tmax, double console, double file);
			/// Returns the simulation vector, used by Integrator to get a handle on the sim vector for derivatives.
			std::vector<Block*> sim()
			{
				return simulation;
			};
			Clock *clock;								///< Clock reference.
		private:
			double rptRate;								///< rpt() output rate
			std::vector<Block*>simulation;				///< Simulation vector 
			Integrator *i;								///< Integrator object
		};
	}
}