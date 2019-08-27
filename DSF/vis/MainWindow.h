#pragma once

#include "netCallback.h"
#include "tblCallback.h"
#include "scene.h"
#include "cameraBase.h"

#include <fx.h>
#include <fx3d.h>

#include <iostream>


	// networking
#include "net/NetClient.h"
#include "net/msg.h"
#include "net/data.h"


namespace dsf
{
	namespace vis
	{
		class RenderThread;
		class MainWindow : public FXMainWindow 
		{
			FXDECLARE(MainWindow)

		public:
			MainWindow(FXApp *a, double tmin, double tmax, double dt);
			virtual ~MainWindow() {};
			void create();

			enum 
			{
				ID_CANVAS = FXMainWindow::ID_LAST,
				ID_PLAY,
				ID_FRAME,
				ID_FRAMEBACK,
				ID_STOP,
				ID_RESET,
				ID_RATEMODTEN,
				ID_RATEMODPOINTONE,
				ID_FILEOPEN,
				ID_VIEWONE,
				ID_VIEWTWO,
				ID_VIEWTHREE,
			};

			// messages
			long onRefresh	(FXObject *, FXSelector, void*);
			long onView		(FXObject *, FXSelector, void*);
			long onLeftClick(FXObject *, FXSelector, void*);
			long onRightClick(FXObject*, FXSelector, void*);
			long onMouseWheel(FXObject*,FXSelector, void*);
			long onfileopen(FXObject*,FXSelector, void*);
			long drawScene(FXObject*,FXSelector, void*);

		protected:
			MainWindow() {};

		private:
			FXGLCanvas	*glCanvas;
			FXGLVisual	*glVisual;
			FXVerticalFrame *buttonFrame;	// public so we can add toolbars on the fly

			// camera position and orientation
				
				/// perspective to use for view
			int perspective;

				/// store last positions for click dragging
			double x,y;

			/// Scene manages the osg::SceneView object.
			Scene *s;

			/// Rendering thread.
			RenderThread *render;

			/// Camera vector.
			std::vector<cameraBase *>camera;

			/// Status bool. Prevents a null world from rendering (and crashing visualization).
			bool worldConfigured;

			/// network access
			NetClient * net;
		};
	}
}