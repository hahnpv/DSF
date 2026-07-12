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
		namespace {
		/// Make this Sim's registries the thread's active ones for the
		/// duration of a lifecycle call (RAII: restores the previous
		/// context on scope exit, so nesting and exceptions are safe). [R1]
		struct ScopedSimContext
		{
			TClassIntegrandDict<Block>* prev_i;
			EventBus* prev_e;
			ScopedSimContext(TClassIntegrandDict<Block>* i, EventBus* e)
				: prev_i(TClassIntegrandDict<Block>::current()),
				  prev_e(EventBus::current())
			{
				TClassIntegrandDict<Block>::make_current(i);
				EventBus::make_current(e);
			}
			~ScopedSimContext()
			{
				TClassIntegrandDict<Block>::make_current(prev_i);
				EventBus::make_current(prev_e);
			}
		};
		} // namespace

		void Sim::run() 
		{
			init();
			exec();
		}

		void Sim::init()
		{
			ScopedSimContext ctx(&integrands_, &events_);
			dsf::util::TFunctor<Block>(simulation, &Block::init);
		}

		void Sim::step()
		{
			// Guard against stepping an unloaded Sim (clock/integrator are only
			// created by load()). Without this, dsf.Sim().step() from Python is
			// a null-deref segfault instead of a catchable error. [A7]
			if (!clock || !i || simulation.empty())
				throw std::runtime_error("Sim::step() called before Sim::load()");
			ScopedSimContext ctx(&integrands_, &events_);
			i->propagate(simulation[0]);							// integrate
			EventBus::Instance()->evaluate(clock->t(), clock->dt());	// event detection
			EventBus::Instance()->latch();							// save state for next step
			dsf::util::TFunctor<Block>(simulation, &Block::rptSim);	// report
		}

		void Sim::finalize()
		{
			ScopedSimContext ctx(&integrands_, &events_);
			dsf::util::TFunctor<Block>(simulation, &Block::rpt);		// final report, all models.
			dsf::util::TFunctor<Block>(simulation, &Block::finalize);
		}

		void Sim::exec()
		{
			if (!clock || !i || simulation.empty())
				throw std::runtime_error("Sim::exec() called before Sim::load()");
			ScopedSimContext ctx(&integrands_, &events_);

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
			ScopedSimContext ctx(&integrands_, &events_);

			// Start from a clean integrand table and event bus — OUR OWN (R1):
			// this makes re-load() on the same Sim instance well-defined and,
			// unlike the old global clear, cannot wipe another live Sim's
			// registered state out from under it.
			integrands_.clear();
			events_.clear();

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