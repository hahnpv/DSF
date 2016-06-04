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

namespace dsf
{
	namespace vis
	{
		/// A base class for actor-driving callbacks.
		/// This callback is placed as a child of a PositionAttiudeTransform, and manipulates
		/// the transform by updating the PositionAttitudeTransform as a function of the table values, driven by the frameStamp
		class baseCallback : public osg::NodeCallback
		{
		public:
			baseCallback()
			{}

				/// Return the position of the actor, specifically used by RenderThread (and camera?)
			virtual osg::Vec3 get_position()
			{
				return position;
			};

				/// The overloaded operator() is the method by which OSG calls the callback.
			virtual void operator()( osg::Node* node, osg::NodeVisitor* nv )
			{				
				// Continue traversing scene graph
				traverse( node, nv );
			}

		protected:
			osg::Vec3 position;		// current position and orientation
			osg::Vec3 orientation;	//
		};
	}
}