#pragma once

//#include <osg/Timer>
//#include <osg/FrameStamp>

namespace dsf
{
	namespace sim 
	{
/*		/// A real time clock. For use with real-time visualization.
		/// Incomplete.

		/// on set(false), need to freeze clock value and calculate dt
		/// divide by 2, return new time on each increment (2 calls)
		/// that should be it (?)
		/*
					frameNumber = 0;
			start_tick = timer.tick() - (frameStamp->getReferenceTime()/timer.getSecondsPerTick());
			while (frameStamp->getReferenceTime() <= tmax) 
			{	
				double elapsedtime = rate*timer.delta_s( start_tick, timer.tick());
				double delta = elapsedtime - frameStamp->getReferenceTime();

				_frame(delta);
			
				if (pause)			// kill condition
				{
					pause = false;
					break;
				}
			}		
		
		
		class RTClock 						// a digital clock 
		{
		public:
			
			/// This method is required for the function pointer instantiation.
			Clock() {};	

			/// Create a new clock with a specified integration rate.
			/// \param dt Integration rate
			Clock(double dt) 
			{
				time   = 0;
				error  = (1/dt)*2.0;
			}

			/// Return the current simulation time in seconds.
			double t()  { 
				return (double)time/error; 
			}

			/// Set a new integration rate during the simulation.
			/// This has been verified and appears working, however use at your own risk.
			/// Watch variables carefully as they pass through the transition.
			/// Only set while sample() returns true, IE, not mid integration cycle.
			/// \param newdt new integration rate.
			void set_dt(double newdt)						// EXPERIMENTAL & UNVALIDATED
			{	
				double derror =0;							// need to avoid setting mid-integration
				if ( (derror = (1/newdt)*2.0) == error)		// don't reset if it is the same
					return;
				derror /= error;							// ratio of errors
				error = (1/newdt)*2.0;
				time  = (int) ( (double)time * derror); 
			}

			/// Return the current integration rate.
			double dt() 
			{ 
				return 2.0/error;			// dt = 2 ticks for a RK integrator
			}

			/// A dual-use sample function.
			/// If t=0, it returns true if the sim is not mid-integration, and false if 
			/// the simulation is currently in the middle of an integration cycle.     \n
			/// If t != 0, then it checks if the current sim time is a multiple of the 
			/// requested time, and returns true if so.
			/// \param t Test time.
			bool Sample(double t) {			// sample at a regular interval, return true/false
				if ( t == 0 || !safe_sample)
					return safe_sample;
				if ( time / (t*error) == (int)(time / (t*error)) )
					return true;
				else
					return false;
			}

			/// Increment the simulation clock by dt/2.
			/// deprecated here
			void increment() 
			{
				time++;
			}

			/// Set the state of the integrator.
			void set(bool safe_sample) 
			{
				this->safe_sample = safe_sample;
			}
		private:
			double error;					///< Error parameter to convert time in ticks to seconds.
			bool safe_sample;				///< Simulation state.
			unsigned long int time;			///< Time in ticks.

			// real time clock via OSG
			unsigned int frameNumber;
			osg::Timer_t start_tick;
			osg::Timer timer;

		};
		*/
	}
}