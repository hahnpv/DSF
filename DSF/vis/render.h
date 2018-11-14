#pragma once

#include <fx.h>
#include <FXThread.h>

#include <osg/Timer>
#include <osg/FrameStamp>

#include <iostream>
#include <vector> 
namespace dsf
{
	namespace vis
	{
			/// RenderThread is the rendering context
			/// RenderThread holds the time base and pings MainWindow whenever the scene needs an update
			/// needs a slight re-tooling to decouple from MainWindow, so that other visualizations can be used
		class RenderThread : public FXThread, public FXObject
		{
			FXDECLARE(RenderThread)
		public:
			RenderThread(FXApp *a, FXObject *b,double tmin, double tmax, double dt);
			~RenderThread() {};

			enum 
			{
				ID_REFRESH,
			};

			FX::FXint run();										// run a simulation

				/// Invoke the thread for simulation playback
			long play(FXObject*,FXSelector, void*)
			{
				start();
				return 0;
			}
			
				/// Stop the simulation on the next frame
			long stop(FXObject*,FXSelector, void*)
			{	
				pause = true;
				return 0;
			};

			long frame(FXObject*,FXSelector, void*);				// advance a single frame
			long frameBack(FXObject*,FXSelector, void*);			// reverses a single frame
			long reset(FXObject*,FXSelector, void*);				// reset simulation
			
				/// Modify the playback rate of the simulation
			long rate_mod(FXObject*,FXSelector sel, void*);

			osg::FrameStamp *frameStamp;

		protected:
			RenderThread() {};
		private:
			void _frame(double dt);			// advance the simulation 1 frame. all visualization members use this method.
			
			double dt;				///< time increment for frame steps, specified in constructor
			double tmin;			///< start time
			double tmax;			///< max time

			unsigned int frameNumber;
			osg::Timer_t start_tick;
			osg::Timer timer;

			double rate;			///< user-selectable rate modifier
			bool pause;				// pause variable, set it using
									// stop button.

			FXGUISignal *notify;	///< notification object to communicate with FOX window
		};
	}
}