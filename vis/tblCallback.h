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

#include "../util/tbl/tbl2d.h"

#include "baseCallback.h"

namespace dsf
{
	namespace vis
	{
		/// A table-driven callback.
		/// This callback is placed as a child of a PositionAttiudeTransform, and manipulates
		/// the transform by updating the PositionAttitudeTransform as a function of the table values, driven by the frameStamp
		class tblCallback : public baseCallback
		{
		public:
			tblCallback(std::string filename,double tmin, double tmax) : _tbl(filename)
			{
				this->tmin = tmin;
				this->tmax = tmax;
			}

				/// The overloaded operator() is the method by which OSG calls the callback.
			virtual void operator()( osg::Node* node, osg::NodeVisitor* nv )
			{
				double t = nv->getFrameStamp()->getReferenceTime();

				std::vector< double> results = _tbl.interp(t);

				osg::PositionAttitudeTransform* pat = dynamic_cast<osg::PositionAttitudeTransform*>(node);

				position[0] = results[pos[0]];
				position[1] = results[pos[1]];
				position[2] = results[pos[2]];
			
				orientation[0] = results[orient[0]];
				orientation[1] = results[orient[1]];
				orientation[2] = results[orient[2]];
				
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

				/// Set the columns to observe in the input file.
				/// No error/bound checking.
				/// \param *p int[3] containing the x,y,z file headers
				/// \param *p int[3] containing the phi,theta,psi file headers
			void setFileHeaders( double *p, double *o)
			{
				pos = new double[3];
				pos[0] = p[0];
				pos[1] = p[1];
				pos[2] = p[2];

				orient = new double[3];
				orient[0] = o[0];
				orient[1] = o[1];
				orient[2] = o[2];
			}

		protected:
			double *pos;			// columns to look for in the file
			double *orient;			//

			double tmin;
			double tmax;

			dsf::util::Table2d _tbl;
		};
	}
}