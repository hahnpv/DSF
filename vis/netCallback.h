#pragma once 

#include <osgViewer/Viewer>
#include <osgGA/TrackballManipulator>
#include <osg/NodeCallback>
#include <osg/Camera>
#include <osg/Group>
#include <osg/MatrixTransform>
#include <osgDB/ReadFile>

#include <osg/PositionAttitudeTransform>

#include <iostream>
using namespace std;

#include "baseCallback.h"

#include "render.h"

#include "../util/tbl/tbl2d.h"

#include "../net/net.h"
#include "../net/data.h"

namespace dsf
{
	namespace vis
	{
		/// A table-driven callback.
		/// This callback is placed as a child of a PositionAttiudeTransform, and manipulates
		/// the transform by updating the PositionAttitudeTransform as a function of the table values, driven by the frameStamp
		class netCallback : public baseCallback
		{
		public:
			netCallback()
			{
				frameCount = 0;
			}

				/// The overloaded operator() is the method by which OSG calls the callback.
			virtual void operator()( osg::Node* node, osg::NodeVisitor* nv )
			{
				osg::PositionAttitudeTransform* pat = dynamic_cast<osg::PositionAttitudeTransform*>(node);

				// need to check for render->running, otherwise you'll advance sim by just orbiting!
				if ( frameCount == 0)
				{
					get_data();
					frameCount++;
				}

				if( render->running() )
				{
					get_data();
				}

				pat->setPosition( position );

					// This corresponds to direct NED input
				pat->setAttitude( 
					osg::Quat(
						orientation[0], osg::Vec3(0,1,0),
						orientation[1], osg::Vec3(0,0,1),
						orientation[2], osg::Vec3(1,0,0)
					)
				);

					// Continue traversing scene graph
				traverse( node, nv );
			}

			void setNet(Net & net, RenderThread & render)
			{
				this->net = &net;
				this->render = &render;
			}

		protected:

			void get_data()
			{
				data d;
				d = net->receive<data>();

//				cout << "net callback" << endl;

				if (frameCount % 100 == 0)
					cout << "[render] data: " << d.x << " " << d.y << " " << d.z << " " << d.phi << " " << d.theta << " " << d.psi << " " << d.t << endl;			

				position[0] = d.x;
				position[1] = d.y;
				position[2] = d.z;

				orientation[0] = d.phi;
				orientation[1] = d.theta;
				orientation[2] = d.psi;

				frameCount++;
			}

			int frameCount;
			Net * net;							// net access
			RenderThread * render;				// to get status of rendering (net blocking)
		};
	}
}