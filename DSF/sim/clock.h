#pragma once

#include <iostream>

namespace dsf
{
	namespace sim 
	{
		/// A digital clock. All core time calculations are done with integers,
		/// resulting in no round-off errors that must be corrected as the simulation proceeds.
		/// The only time a double appears is in the return values, by type conversion with an
		/// error function. The error function is 2/dt. This is because the clock updates twice per
		/// integration cycle. 
		class Clock
		{
		public:
			Clock() {};				///< This method is required for the function pointer instantiation.

			/// Create a new clock with a specified integration rate.
			/// \param dt Integration rate
			Clock(double _dt, double _tmax) 
			{
				time  = 0;
				error = (1/_dt)*2.0;
				state = true;
				maxtime  = _tmax;
			}

			double t()  			///< Return the current simulation time in seconds.
			{ 
				return (double)time/error; 
			}

			double tmax()			///< Return the maximum simulation time
			{
				return maxtime;
			}

			/// Set a new integration rate during the simulation.
			/// This has been verified and appears working, however use at your own risk.
			/// Watch variables carefully as they pass through the transition.
			/// Only set while sample() returns true, IE, not mid integration cycle.
			/// \param newdt new integration rate.
			void set_dt(double newdt)						// EXPERIMENTAL & UNVALIDATED
			{
				if (!Sample(0.))
					return;

//				std::cout << "setting dt: " << newdt << " was: " << dt() << std::endl;
				double derror =0;							// need to avoid setting mid-integration
				if ( (derror = (1/newdt)*2.0) == error)		// don't reset if it is the same
					return;
				derror /= error;							// ratio of errors
				error = (1/newdt)*2.0;
				time  = (int) ( (double)time * derror); 
			}

			double dt() 									///< Return the current integration rate.
			{ 
				return 2.0/error;			// dt = 2 ticks for a RK4 integrator; may need to make variable for RKn, ABM, etc.
			}

			/// A dual-use sample function.
			/// If t=0, it returns true if the sim is not mid-integration, and false if 
			/// the simulation is currently in the middle of an integration cycle.     \n
			/// If t != 0, then it checks if the current sim time is a multiple of the 
			/// requested time, and returns true if so.
			/// \param t Test time.
			bool Sample(double t)
			{
				if ( t == 0 || !safe_sample)
					return safe_sample;
				if ( time / (t*error) == (int)(time / (t*error)) )
					return true;
				else
					return false;
			}

			void increment() 							///< Increment the simulation clock by dt/2.
			{
				time++;
			}

			void set(bool _safe_sample) 				///< Set the state of the integrator.
			{
				safe_sample = _safe_sample;
			}

			void end()									///< End simulation
			{
				state = false;
			}

			bool is_running()
			{
				return state;
			}
		private:
			double error;					///< Error parameter to convert time in ticks to seconds.
			double maxtime;					///< Maximum simulation time.
			bool safe_sample;				///< Simulation state.
			unsigned long int time;			///< Time in ticks.
			bool state;						///< sim state; true=ok to run; false=end sim.
		};
	}
}
