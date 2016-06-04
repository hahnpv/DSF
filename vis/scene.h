#pragma once

#include <osg/Group>
#include <osg/FrameStamp>
#include <osgUtil/SceneView>

#include "cameraBase.h"

namespace dsf
{
	namespace vis
	{
			/// Scene manages the OSG SceneView object.
		class Scene 
		{
		public:
			Scene()
			{
				configured = false;
			}

				/// Creates a SceneView object with a given width and height
				/// \param width Width of the scene
				/// \param height Height of the scene
			void create(int width, int height)
			{
				rootNode = new osg::Group;					// empty now until file dialog
				scene    = new osgUtil::SceneView;
				scene->setViewport(0,0,width, height);
				scene->setDefaults();

					// prevent culling due to the extreme size difference of projectile and wgs84 earth
				scene->setComputeNearFarMode(osg::CullSettings::DO_NOT_COMPUTE_NEAR_FAR);
				scene->setSceneData( rootNode );
			}

				/// on a resize of the UI, viewport must be updated
			void setViewport(int width, int height)
			{
				scene->setViewport(0,0,width,height);
			}

				/// Draw the scene given a view matrix and a frame stamp
			void draw(cameraBase *camera, osg::FrameStamp *f)
			{
				scene->setFrameStamp( f );
				scene->update();
				scene->setViewMatrix( camera->getViewMatrix() );
				scene->cull();
				scene->draw();
			}

			osg::Group	*rootNode;
		private:
			bool configured;
			osgUtil::SceneView *scene;
		};
	}
}