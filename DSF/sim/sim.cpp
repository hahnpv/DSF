#include <time.h>
#include <stdexcept>

#include "sim.h"
#include "integrator_base.h"
#include "event.h"
#include "integratorRK4.h"
#include "integrator_rk45.h"
#include "integrator_verlet.h"
#include "block.h"
#include "TClassDict.h"
#include "TIntDict.h"
#include "../util/TFunctor.h"

// Explicit instantiation of factory dictionary to ensure singleton is in libDSF.so
template class dsf::sim::TClassDict<dsf::sim::Block>;

using namespace dsf::util;

namespace dsf
{
	namespace sim 
	{
		void Sim::run() 
		{
			init();
			exec();
		}

		void Sim::init()
		{
			dsf::util::TFunctor<Block>(simulation, &Block::init);
		}

		void Sim::step()
		{
			// Guard against stepping an unloaded Sim (clock/integrator are only
			// created by load()). Without this, dsf.Sim().step() from Python is
			// a null-deref segfault instead of a catchable error. [A7]
			if (!clock || !i || simulation.empty())
				throw std::runtime_error("Sim::step() called before Sim::load()");
			i->propagate(simulation[0]);							// integrate
			EventBus::Instance()->evaluate(clock->t(), clock->dt());	// event detection
			EventBus::Instance()->latch();							// save state for next step
			dsf::util::TFunctor<Block>(simulation, &Block::rptSim);	// report
		}

		void Sim::finalize()
		{
			dsf::util::TFunctor<Block>(simulation, &Block::rpt);		// final report, all models.
			dsf::util::TFunctor<Block>(simulation, &Block::finalize);
		}

		void Sim::exec()
		{
			if (!clock || !i || simulation.empty())
				throw std::runtime_error("Sim::exec() called before Sim::load()");

			time_t seconds = time(NULL);

			while ( (clock->t() < clock->tmax()) && clock->is_running() )
			{
				step();
			}

			finalize();

			cout << "Sim run time: " << time(NULL) - seconds << endl;
		}

		/// Provides the initial configuration of a simulation.
		/// Sets the output and clock references in each Block object and 
		/// time constraints.
		void Sim::load(Block * root, double _dt, double _tmax, double _console, double _file) 
		{
			load(root, _dt, _tmax, _console, _file, "RK4", 1e-8, 1e-6);
		}

		void Sim::load(Block * root, double _dt, double _tmax, double _console, double _file,
		               const std::string& integrator_type, double atol, double rtol)
		{
			rptRate = _console;

			// Start from a clean integrand table and event bus. In a long-lived
			// process (GUI / MCP session / Monte Carlo) a previous run's state
			// pointers would otherwise still be registered and get integrated.
			TClassIntegrandDict<Block>::Instance()->clear();
			EventBus::Instance()->clear();

			// Validate timing parameters. A missing/zero dt attribute previously
			// produced error=inf and an infinite loop with zero state advance.
			if (_dt <= 0.0)
			{
				std::cerr << "Sim::load: invalid dt=" << _dt
				          << " (must be > 0); aborting run" << std::endl;
				clock = new Clock(1.0, 0.0);
				clock->end();				// exec() loop will not run
				output = new Output(_file);
				simulation.push_back(root);
				simulation.push_back(output);
				return;
			}
			if (_tmax <= 0.0)
			{
				std::cerr << "Sim::load: tmax=" << _tmax
				          << " (must be > 0); simulation will not advance" << std::endl;
			}

			// Instantiate clock and output
			clock = new Clock( _dt, _tmax );
			output = new Output( _file);

			// Integrator factory
			if (integrator_type == "RK45" || integrator_type == "rk45") {
				auto* rk45 = new IntegratorRK45(atol, rtol);
				rk45->set_step_bounds(_dt * 0.01, _dt * 100.0);
				i = rk45;
				cout << "Integrator: Dormand-Prince RK45 (atol=" << atol << ", rtol=" << rtol << ")" << endl;
			} else if (integrator_type == "Verlet" || integrator_type == "verlet") {
				i = new IntegratorVerlet;
				cout << "Integrator: Stormer-Verlet (symplectic)" << endl;
			} else {
				i = new IntegratorRK4;
				if (integrator_type != "RK4" && integrator_type != "rk4" && !integrator_type.empty())
					cout << "Warning: Unknown integrator '" << integrator_type << "', defaulting to RK4" << endl;
				else
					cout << "Integrator: RK4 (fixed-step)" << endl;
			}
			i->clock = clock;

			// add output to the simulation vector
			simulation.push_back( root);
			simulation.push_back( output);
			TFunctor<Block, Output>(&Block::OutputRef, simulation, *output);			// set Output reference in each Block
			TFunctor<Block, Clock>(&Block::ClockRef,   simulation, *clock);				// Set the Clock reference in each Block
		}

		void Sim::setXmlInfo(const std::string& xml_file, const std::string& xml_content)
		{
			if (!output) return;

			// Extract basename without extension for output filenames
			std::string basename = xml_file;
			// Strip path
			auto pos = basename.find_last_of("/\\");
			if (pos != std::string::npos) basename = basename.substr(pos + 1);
			// Strip .xml extension
			pos = basename.rfind(".xml");
			if (pos != std::string::npos) basename = basename.substr(0, pos);

			output->setBaseName(basename);
			output->setMetadata(xml_file, xml_content, clock->dt(), clock->tmax());
		}
	}
}