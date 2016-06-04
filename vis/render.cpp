#include "render.h"
#include <iostream>

#include <osg/Vec3>
#include <osg/Node>
#include <osg/Geometry>
#include <osg/ShapeDrawable>

#include <osg/FrameStamp>

#include "MainWindow.h"

using namespace std;

namespace dsf
{
	namespace vis
	{
		FXDEFMAP(RenderThread) RenderThreadMap[] = {
			FXMAPFUNC( SEL_COMMAND,	MainWindow::ID_PLAY,  RenderThread::play),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_FRAME, RenderThread::frame),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_FRAMEBACK, RenderThread::frameBack),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_RESET, RenderThread::reset),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_STOP, RenderThread::stop),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_RATEMODTEN,		RenderThread::rate_mod),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_RATEMODPOINTONE,	RenderThread::rate_mod),
		};

		FXIMPLEMENT(RenderThread,FXObject,RenderThreadMap,ARRAYNUMBER(RenderThreadMap));

			/// Custom constructor
			/// \param *a FXApp reference
			/// \param *b FXObject reference
			/// \param tmin Start time of the simulation
			/// \param tmax Maximum simulation time
			/// \param dt Step time for the frame commands
		RenderThread::RenderThread(FXApp *a, FXObject *b, double tmin, double tmax, double dt) : FXObject(*b)
		{
			notify = new FXGUISignal(a,b,RenderThread::ID_REFRESH);
			frameStamp = new osg::FrameStamp;

			rate = 1.0;
			pause = false;
			this->tmin = tmin;
			this->tmax = tmax;
			this->dt = dt;

//			network = false;
		}

			/// The render thread, invoked by play()
		FX::FXint RenderThread::run() 				// Iterate over all actors and update positions ... "play"
		{											// what about play backwards?
			cout << "hit play" << endl;
	
			frameNumber = 0;
			start_tick = timer.tick() - (frameStamp->getReferenceTime()/timer.getSecondsPerTick());
			while (frameStamp->getReferenceTime() <= tmax) 
			{	
				double elapsedtime = rate*timer.delta_s( start_tick, timer.tick());
				double delta = elapsedtime - frameStamp->getReferenceTime();

				_frame(delta);		// this should work universally, so long as when we
									// are using net, nothing is dependant on frame timestamp
									// will (eventually) want to sync frame stamp to net stamp

				if (pause)			// kill condition
				{
					pause = false;
					break;
				}
			}
			return (FX::FXint)1;
		}

			/// render a single frame
		void RenderThread::_frame(double dt)
		{
			// check if max or min time are exceeded, otherwise set new time
			if ( frameStamp->getReferenceTime()+dt > tmax)
			{
				frameStamp->setReferenceTime( tmax);
			}
			if ( frameStamp->getReferenceTime()+dt < tmin)
			{
				frameStamp->setReferenceTime( tmin);
			}
			else
				frameStamp->setReferenceTime( frameStamp->getReferenceTime() + dt);

			frameStamp->setFrameNumber( frameNumber++ );
			notify->signal();
		}

			/// Frame forward by dt.
		long RenderThread::frame(FXObject*,FXSelector, void*) 
		{
			if (!running())
			{
				_frame(dt);
			}
			return 0;
		}

			/// Frame backwards by dt.
		long RenderThread::frameBack(FXObject*,FXSelector, void*) 
		{
			if (!running())
			{
				_frame(-dt);
			}
			return 0;
		}

			/// Reset the simulation
		long RenderThread::reset(FXObject*,FXSelector, void*) 
		{
			if (!running())
			{
				frameStamp->setReferenceTime( 0.0 );
				_frame(0.0);
			}
			pause = false;				// if sim is running and you hit reset, it will keep playing. Hit stop to stop :)	
			return 0;
		}

		long RenderThread::rate_mod(FXObject*,FXSelector sel, void*)
		{
			unsigned int selid = FXSELID(sel);
			if (selid == MainWindow::ID_RATEMODTEN) 
			{
				rate *= 10;
			}
			else if (selid == MainWindow::ID_RATEMODPOINTONE) 	
			{
				rate *= 0.1;
			}
			return 0;
		}
	}
}