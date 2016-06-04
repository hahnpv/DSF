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
		/// Camera Base Class
		/// All cameras derive off this class, allowing all cameras to be placed in
		/// a container. Defines basic camera interface.
		class cameraBase : public osg::NodeCallback 
		{
		public:
		   cameraBase()
		   {
		   } 

		   /// Get the view matrix of the camera for SceneView.
		  virtual osg::Matrixd getViewMatrix() { return viewMatrix;}; 

		   /// Generic three-component update function, to be overloaded by derived classes.
		  virtual void update(double, double, double) {};
		   
		protected:
			osg::Matrixd viewMatrix; 
		};
	}
}
