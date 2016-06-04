#pragma once 

#include "tblCallback.h"

#include <osgViewer/Viewer>
#include <osgGA/TrackballManipulator>
#include <osg/NodeCallback>
#include <osg/Camera>
#include <osg/Group>
#include <osg/MatrixTransform>
#include <osgDB/ReadFile>

#include <osg/PositionAttitudeTransform>

#include <iostream>

#include "cameraBase.h"
using namespace std;

namespace dsf
{
	namespace vis
	{
			/// A statically positioned camera node focused on a foreign node.
			/// staticCam a callback placed on a PositionAttitudeTransform or a object node, etc. 
			// Right now tightly coupled to RotateCB (which needs a renaming) to get position
		class staticCam : public cameraBase
		{
		public:
			staticCam()
			{
			} 

				/// Set the node in the scene graph to watch
			void setNode( baseCallback &n)
			{
				this->n = &n;
			}

				/// Overloaded operator(), performs the view matrix manipulation
			virtual void operator()(osg::Node* node, osg::NodeVisitor* nv)
			{ 
					// bullet's matrix, from which we can derive our position
				osg::Matrixd targetMatrix = osg::computeLocalToWorld(nv->getNodePath());
				osg::Vec3 camera = targetMatrix.getTrans();

				osg::Vec3 up(1,0,0);

				viewMatrix.makeLookAt(camera,n->get_position(),up);		// crash here (?) virtual?

				traverse(node, nv);
			}

		private:
			baseCallback *n;
			
		};
	}
}