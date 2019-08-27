#include "MainWindow.h"
#include "xmlinput.h"
#include <iostream>
#include "render.h"


#include "findNode.h"
#include "findCallbackNode.h"

#include <osgGA/KeySwitchMatrixManipulator>

using namespace std;
#include "render.h"


namespace dsf
{
	namespace vis
	{
			//
			//	need to look into the on-the-fly remapping, for when cameras are added,
			//	to generate buttons, id's and targets.
			//
		FXDEFMAP(MainWindow) MainWindowMap[] = {
			FXMAPFUNC( SEL_IO_READ, RenderThread::ID_REFRESH,	MainWindow::drawScene),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_VIEWONE,		MainWindow::onView),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_VIEWTWO,		MainWindow::onView),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_VIEWTHREE,	MainWindow::onView),
			FXMAPFUNC( SEL_COMMAND, MainWindow::ID_FILEOPEN,	MainWindow::onfileopen),
			FXMAPFUNC( SEL_LEFTBUTTONPRESS, 	MainWindow::ID_CANVAS,	MainWindow::onLeftClick),
			FXMAPFUNC( SEL_LEFTBUTTONRELEASE, 	MainWindow::ID_CANVAS,	MainWindow::onLeftClick),
			FXMAPFUNC( SEL_MOUSEWHEEL, 	MainWindow::ID_CANVAS,	MainWindow::onMouseWheel),
			FXMAPFUNC( SEL_MOUSEWHEEL, 	MainWindow::ID_CANVAS,	MainWindow::onMouseWheel),
		};

		FXIMPLEMENT(MainWindow,FXMainWindow,MainWindowMap,ARRAYNUMBER(MainWindowMap));

			/// MainWindow is a stand-alone simulation visualization app. 
		MainWindow::MainWindow(FXApp *a, double tmin, double tmax, double dt):FXMainWindow(a,"DSF Visualizer",NULL,NULL,DECOR_ALL,0,0,800,600) 
		{
			// temporary override on tmax -> need to re-think this with the network paradigm
			tmax = 1000;
			dt = 0.01;

			// init renderer
			render = new RenderThread(a, this,tmin,tmax,dt);

			// init scene
			s = new Scene;

			// null net reference until used
			net = 0;


			// opengl visual / panel and vertical frame for buttons to dock into 
			FXHorizontalFrame *glPanel = new FXHorizontalFrame(this,LAYOUT_SIDE_TOP|LAYOUT_FILL_X|LAYOUT_FILL_Y);//,0,0,800,600, 0,0,0,0, 0,0);
			
			glVisual = new FXGLVisual (getApp(), VISUAL_DOUBLEBUFFER);

			glCanvas = new FXGLCanvas(glPanel, glVisual, this, ID_CANVAS, LAYOUT_FILL_X|LAYOUT_FILL_Y|LAYOUT_TOP|LAYOUT_LEFT);

			buttonFrame = new FXVerticalFrame(glPanel, FRAME_GROOVE|LAYOUT_TOP|LAYOUT_LEFT|LAYOUT_FILL_Y,0,0,300,600,10,10,10,10,0,0);
				new FXButton(buttonFrame, " Open File ", NULL,this,ID_FILEOPEN,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);

			// new
			perspective = 0;

			worldConfigured = false; // false until the sim is loaded and configured
		}

			/// drawScene refreshes the scene if the simulation is configured.
		long MainWindow::drawScene(FXObject*,FXSelector, void*) 
		{
			// Make context current
 			if ( glCanvas->makeCurrent() && worldConfigured ) 
			{
				s->setViewport(glCanvas->getWidth(), glCanvas->getHeight());		// hackish, needs to be in a onResize() type fn

				s->draw(camera[perspective], render->frameStamp);

 	 			// Swap buffers if glCanvas is double-buffered
 	 			if(glVisual->isDoubleBuffer()) 
				{
 	   				glCanvas->swapBuffers();
				}

  				// Make context non-current
	  			glCanvas->makeNonCurrent();
			}

			return 0;
		}

			/// Switches the view perspective when a view button is clicked
		long MainWindow::onView(FXObject *, FXSelector sel, void *)
		{
			unsigned int selid = FXSELID(sel);

			perspective = selid - ID_VIEWONE;

			if (!render->running())
			{
				drawScene(0,0,0);
			}
			return 0.0;
		}

			/// Handles left clicks.
			/// On mousedown, saves the mouse position.
			/// On mouseup, takes the difference in position and sends it to the active camera callback.
		long MainWindow::onLeftClick(FXObject *, FXSelector, void *ptr)
		{
			// rotate about bullet
			FXEvent *event=(FXEvent*)ptr;

			// initial click
			if (event->type == 3) 
			{
				x = event->last_x;
				y = event->last_y;
			} 

			// click release
			else if (event->type == 4) 
			{
				double dx, dy;
				dx = x - event->last_x;
				dy = y - event->last_y;

				if (worldConfigured)
					camera[perspective]->update(dx, dy, 0);
			}
			if (!render->running())
			{
				drawScene(0,0,0);
			}
			return 0.0;	
		};

			/// Handles right click actions (void)
		long MainWindow::onRightClick(FXObject*, FXSelector, void*)
		{
			return 0.0;
		};

			/// Handles mouse wheel activities. 
			/// Depending on mouse motion, sends a signal to the current camera callback.
		long MainWindow::onMouseWheel(FXObject*,FXSelector, void *ptr)
		{
			FXEvent *event=(FXEvent*)ptr;
			double dz = 0;
			if ( event->code > 0 ) 
			{
				// scroll in
				dz = -1;
			}
			else if ( event->code < 0 ) 
			{
				// scroll out
				dz = +1;
			}
			if (worldConfigured)
				camera[perspective]->update(0, 0, dz);

			drawScene(0,0,0);

			return 0.0;		// new
		};

			/// Handles the mouse click on the "File Open" dialog.
			/// After the dialog, if a file is selected the xml reader is invoked, which constructs
			/// the scene graph and camera vector.
			/// After that, panels are generated by MainWindow.
			/// Still needs some error checking and control for certain situations.
		long MainWindow::onfileopen(FXObject*,FXSelector, void*)
		{
			FXString filename = FXFileDialog::getOpenFilename(this,"Open a file",FXSystem::getCurrentDirectory()+"\\..\\simulation\\","*.xml");
			std::string filetest(filename.text());

			FXuint useNet = FXMessageBox::question(this,FX::MBOX_YES_NO,"Network or Local Visualisation?","Please select yes for network visualization");
		
			if (filetest.size() != 0)
			{
				cout << "filename selected: " << filename.text() << endl;

				if (useNet == 1)			// 1 == yes, 2 == no
				{
				// stream xml to server
				// need to do this before xml config
					int port = 3490;

					cout << "client" << endl;

					net = new NetClient();

					net->connect("localhost",port);

					net->send_xml_file(filename.text());

//					render->setNetRef(*net);

					// this needs to go into xmlinput
					// once its moved to callback, then set init condx from xml (?)
				//
				}
				else		// verify pointer is null
				{
					net = 0;
				}
				xmlInput xml(filename.text(),*net,*render);

				xml.setRootNode(*s->rootNode);

				camera = xml.getCameras();

				// VCR Controls - invariant, tied to render
				FXVerticalFrame *vcrFrame = new FXVerticalFrame(buttonFrame,FRAME_GROOVE|LAYOUT_FILL_X);
					new FXButton(vcrFrame, "Play", NULL,render,ID_PLAY,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);
					new FXButton(vcrFrame, "Frame",NULL,render,ID_FRAME,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);
					new FXButton(vcrFrame, "FrameBack",NULL,render,ID_FRAMEBACK,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);
					new FXButton(vcrFrame, "Stop", NULL,render,ID_STOP,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);
					new FXButton(vcrFrame, "Reset",NULL,render,ID_RESET,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);

				// Camera - dynamic, depends on cameras defined in XML file
				FXComposite *viewPanelVF = new FXVerticalFrame(buttonFrame,FRAME_GROOVE|LAYOUT_TOP|LAYOUT_FILL_X,0,0,300,0,0,0,0,0);
					new FXLabel(viewPanelVF,"View");
					FXComposite *viewPanel = new FXHorizontalFrame(viewPanelVF,LAYOUT_SIDE_TOP|LAYOUT_FILL_X,0,0,300,0,0,0,0,0);
					for (unsigned int i=0; i<camera.size(); i++)
					{
						FXString label(camera[i]->getName().c_str());
						// the sum on ID_VIEWONE presumes you will have enough ID_VIEW tags available in MainWindow to accomodate size of camera array
						// or size on demand (i think you can do that ... )
						new FXButton(viewPanel, FXString(camera[i]->getName().c_str()), NULL, this,ID_VIEWONE+i,BUTTON_NORMAL,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);
					}

				// Rate Mods - invariant
				FXComposite *ratePanelVF = new FXVerticalFrame(buttonFrame,FRAME_GROOVE|LAYOUT_TOP|LAYOUT_FILL_X,0,0,300,0,0,0,0,0);
					new FXLabel(ratePanelVF,"Rate Modifier");
					FXComposite *ratePanel = new FXHorizontalFrame(ratePanelVF,LAYOUT_SIDE_TOP|LAYOUT_FILL_X,0,0,300,0,0,0,0,0);
						new FXButton(ratePanel, "0.1", NULL, render,ID_RATEMODPOINTONE,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);
						new FXButton(ratePanel, "10", NULL, render,ID_RATEMODTEN,BUTTON_NORMAL|LAYOUT_FILL_X,0,0,0,0,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD,DEFAULT_PAD);

				// to add, recalc buttonFrame and create new children manually
				buttonFrame->recalc();
				vcrFrame->create();
				viewPanelVF->create();
				ratePanelVF->create();

				worldConfigured = true;

				drawScene(0,0,0);		// error here; drawing looks for that callback
			}
			else
			{
				cout << "error opening file" << endl;
			}
			return 0.0;
		}

			/// Create the window.
			/// Invoke parent method's create and show.
			/// Also update the scene class with the width / height of gl area.
		void MainWindow::create() 
		{
			FXMainWindow::create();		// call the parent class' create
			show(PLACEMENT_SCREEN);		// call the show method

			// set up the Scene object
			s->create(glCanvas->getWidth(), glCanvas->getHeight());
		}
	}
}