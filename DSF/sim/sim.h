#pragma once

#include "output.h"
#include <vector>
#include <string>

namespace dsf
{
	namespace sim 
	{
		class Clock;
		class IntegratorBase;
		class Block;

		class Sim {
		public:
			void run();
			void init();
			void step();
			void finalize();
			void exec();
			void load(Block * simulation, double dt, double tmax, double console, double file);
			void load(Block * simulation, double dt, double tmax, double console, double file,
			          const std::string& integrator_type, double atol = 1e-8, double rtol = 1e-6);
			/// Returns the simulation vector, used by Integrator to get a handle on the sim vector for derivatives.
			std::vector<Block*> sim()
			{
				return simulation;
			};
			Clock *clock;								///< Clock reference.
			Output *output;                             ///< Output reference.
		private:
			double rptRate;								///< rpt() output rate
			std::vector<Block*>simulation;				///< Simulation vector 
			IntegratorBase *i;						///< Integrator object
		};
	}
}