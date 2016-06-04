#include <time.h>

#include "sim.h"
#include "integratorRK4.h"
#include "block.h"
#include "../util/TFunctor.h"

using namespace dsf::util;

namespace dsf
{
	namespace sim 
	{
		/// Run a simulation.
		/// This is the core simulation loop.
		void Sim::run() 
		{
			time_t seconds = time(NULL);

			dsf::util::TFunctor<Block>(simulation, &Block::init);

			while ( (clock->t() < clock->tmax()) && clock->is_running() )
			{
				i->propagate(simulation[0]);							// integrate
				dsf::util::TFunctor<Block>(simulation, &Block::rptSim);	// report
			}

			dsf::util::TFunctor<Block>(simulation, &Block::rpt);		// final report, all models.
			dsf::util::TFunctor<Block>(simulation, &Block::finalize);

			cout << "Sim run time: " << time(NULL) - seconds << endl;
		}

		/// Provides the initial configuration of a simulation.
		/// Sets the output and clock references in each Block object and 
		/// time constraints.
		void Sim::load(Block * root, double _dt, double _tmax, double _console, double _file) 
		{
			rptRate = _console;

			// Instantiate clock, output and integrator
			clock = new Clock( _dt, _tmax );
			Output *output = new Output( _file);
			i = new Integrator;
			i->clock = clock;

			// add output to the simulation vector
			simulation.push_back( root);
			simulation.push_back( output);
			TFunctor<Block, Output>(&Block::OutputRef, simulation, *output);			// set Output reference in each Block
			TFunctor<Block, Clock>(&Block::ClockRef,   simulation, *clock);				// Set the Clock reference in each Block
		}
	}
}