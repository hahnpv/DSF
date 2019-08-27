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

#include "staticCamera.h"

using namespace std;

namespace dsf
{
	namespace vis
	{
			/// Camera callback, to be placed under a PositionAttitudeTransform.
			/// This camera can 'orbit' around the target, allowing 360 degree views.
		class orbitCamera : public cameraBase
		{
		public:
			orbitCamera()
			{
				phi = 0;
				theta = 0;
				z = 5;
			} 

				/// Update the camera.
				/// \param dx Change in the x direction, pixels
				/// \param dy Change in the y direction, pixels
				/// \param dz Change in distance from camera to target, absolute value of direction change (-1/+1)
			void update(double dx, double dy, double dz=0)
			{
					// calculate and store numbers to update next call to operator()
				theta   -= (dx)* 0.005;	// theta = hRotation
				phi 	-= (dy)* 0.005;	// phi   = vRotation
			//	double M_PI = 3.14159;
				if (theta >= M_PI * 2)	theta -= M_PI * 2;
				if (theta < 0)			theta += M_PI * 2;
				if (phi >= M_PI * 2)	phi -= M_PI * 2;
				if (phi < 0)			phi += M_PI * 2;

				// scroll in
				if (dz < 0)
					if (z >= 0.30)
						z -= 0.1;

				// scroll out
				if (dz > 0)
					if (z <= 14.9)
						z += 0.1;
			}

				/// Perform the camera manipulation
			virtual void operator()(osg::Node* node, osg::NodeVisitor* nv)
			{ 
					// bullet's matrix, from which we can derive location
				osg::Matrixd targetMatrix = osg::computeLocalToWorld(nv->getNodePath());
				target = targetMatrix.getTrans();
			
					// using phi/theta/psi, derive cam position (x is up)
				osg::Vec3 camera;
				camera[2] = z * cos(phi) * cos(theta);
				camera[0] = z * sin(phi);
				camera[1] = z * cos(phi) * sin(theta);

				osg::Vec3 up(1,0,0);			// up vector
			//	double M_PI = 3.14159;
				if (phi > M_PI/2 && phi < M_PI / 2 * 3)
					up = osg::Vec3(-1,0,0);

				viewMatrix.makeLookAt(target+camera,target,up);

				traverse(node, nv);
			}

		private:

			osg::Vec3 target;

			double phi;
			double theta;
			double z;
		};
	}
}