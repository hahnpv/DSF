#pragma once

#include "../util/xml/xml.h"
#include "../util/xml/xmlnode.h"

// debug printing
#include "../util/xml/xml_reader.h"

#include <osg/Node>
#include <osgDB/ReadFile>

#include "baseCallback.h"
#include "netCallback.h"
#include "tblCallback.h"
#include "orbitCamera.h"
#include "staticCamera.h"
#include "cameraBase.h"

#include "findNode.h"
#include "findCallbackNode.h"

//
//	Input an XML file, parse it and create a scene graph. 
//
namespace dsf
{
	namespace vis
	{
		class xmlInput
		{
		public:
			xmlInput(std::string filename, NetClient & net, RenderThread & render)
			{
				this->filename = filename;
				this->net = &net;
				this->render = &render;
			}

			/// find and configure each sim class by their <visualization> tag
			/// network tag specifies whether or not data is coming from the network
			/// which influences the callback used on actors (netCallback v. tblCallback)
			/// (null network = no network)
			void parse(dsf::xml::xmlnode n,osg::Group &root)
			{
				// each node at this point is considered an "actor"
				cout << "number of <sim> children: ";
				cout << n.children().size() << endl;
				
				// actors (2, earth and bullet)
				for (unsigned int i=0; i<n.children().size(); i++)
				{
					n.child(i);
					cout << "actor: " << n.name() << endl;
					
					if (n.findChild("visualization"))
					{
						std::string name = "";
						if (n.findAttr("name"))
						{
							name = n.attrAsString("name");
						}
						n.search("visualization");
						// parse through actors
						cout << "Actor " << i << " " << n.name() << endl;

						osg::Node *Bullet;

						if ( n.findAttr("model") )
						{
							cout << "model tag speficied " << n.attrAsString("model") << endl;
							Bullet = osgDB::readNodeFile(n.attrAsString("model"));
							cout << "node file read! " << n.attrAsString("model") << endl;
						} else {
							cout << "didn't find model tag!" << endl;
						}
						cout << "name: " << name << endl;
						Bullet->setName(name);

						// static tag - statically placed node
						if ( n.findChild("static") )
						{
							cout << "static tag specified" << endl;
							n.search("static");

							if ( n.findAttr("position") )
							{
								cout << "static location tag specified" << endl;
							}
							if ( n.findAttr("orientation") )
							{
								cout << "static orientation tag specified" << endl;
							}

							// ignoring tags for now ... 
							root.addChild(Bullet);

							n.parent();
						}

						// data tag - read-from-file node
						if ( n.findChild("data") )
						{
							cout << "data tag specified" << endl;
							n.search("data");
						
							std::string input = "";
							if ( n.findAttr("file") )
							{
								cout << "file tag speficied" << endl;
								input = n.attrAsString("file");
							}
							double position[3];
							if ( n.findAttr("position") )
							{
								cout << "location tag specified" << endl;
								position[0] = n.attrAsVec3("position").x;
								position[1] = n.attrAsVec3("position").y;
								position[2] = n.attrAsVec3("position").z;
							}
							double orientation[3];
							if ( n.findAttr("orientation") )
							{
								cout << "orientation tag specified" << endl;
								orientation[0] = n.attrAsVec3("orientation").x;
								orientation[1] = n.attrAsVec3("orientation").y;
								orientation[2] = n.attrAsVec3("orientation").z;
							}

							// need to improve automation / configuration of this
							osg::ref_ptr<osg::PositionAttitudeTransform> mtLeft = new osg::PositionAttitudeTransform;
							std::string PATName = name + " PAT\nDYNAMIC";
							cout << "naming PAT: " << PATName << endl;
							mtLeft->setName( PATName );
							mtLeft->setDataVariance( osg::Object::DYNAMIC );

							Bullet->setDataVariance( osg::Object::DYNAMIC );

							if((bool)net)
							{
								cout << "Configuring NETWORK viewer" << endl;
								bulletCallback = new netCallback();
								netCallback *ncb = dynamic_cast<netCallback*>(bulletCallback);
								ncb->setNet(*net,*render);
							}
							else	// table driven
							{
								cout << "Configuring TABLE viewer" << endl;
								bulletCallback = new tblCallback(input,0.00,40.0);
								tblCallback *tcb = dynamic_cast<tblCallback*>(bulletCallback);
								tcb->setFileHeaders(position, orientation);
							}

							std::string CBName = name + " Callback";
							cout << "naming callback: " << CBName << endl;
							bulletCallback->setName( CBName );
							mtLeft->setUpdateCallback( bulletCallback );

							root.addChild( mtLeft.get() );
								mtLeft.get()->addChild( Bullet);		// maybe have to add it to mtLeft.get()?

							n.parent();
						}
				
						n.parent();		// parent from visualization
						n.parent();		// parent from child(i)
					}
					else if ( n.name().compare("visualization") == 0)
					{
						cout << "Found visualization configuration node" << endl;

						// right now the only thing to configure is cameras
						if ( n.findChild("cameras"))
						{
							n.search("cameras");
							cout << n.children().size() << " cameras" << endl;
							for (unsigned int i=0; i<n.children().size(); i++)
							{	
								n.child(i);
								if (n.attrAsString("type").compare("orbit") == 0)
								{
									cout << "orbit camera found" << endl;
									// 1. create orbit node
									orbitCamera *o = new orbitCamera;
									// 2. assign name
									o->setName(n.attrAsString("name"));
									// 3. add to scene graph (manually now, dynamically later using name search)
									root.getChild(0)->asGroup()->getChild(0)->setUpdateCallback( o);
									// 4. add to vector
									cout << "pushing back a camera " << endl;
									cameraVector.push_back( o);
								}
								else if (n.attrAsString("type").compare("static") == 0)
								{
									cout << "static camera found" << endl;
									// 1. create PAT
									osg::PositionAttitudeTransform *pat = new osg::PositionAttitudeTransform;
									// 2. set PAT position
									pat->setPosition( osg::Vec3(6378140,-5,0));
									// 3. create static node
									cout << "3" << endl;
									staticCam *staticCamera = new staticCam; 
									// 3.5. set name
									cout << " Name: " <<n.attrAsString("name") << endl;
									staticCamera->setName(n.attrAsString("name"));
									// 4. add static node to PAT update callback (manually now, dynamically later using callback name search)
									cout << "name set" << endl;
									cout << "callback: " << root.getChild(0)->getUpdateCallback() << endl;
									staticCamera->setNode( *dynamic_cast<baseCallback*>(root.getChild(0)->getUpdateCallback()) ); 
									// 5. set node callback for PAT
									cout << "5" << endl;
									pat->setUpdateCallback( staticCamera);
									// 6. add PAT to scene graph
									root.addChild(pat);
									// 7. add to vector
									cout << "pushing back a camera " << endl;
									cameraVector.push_back( staticCamera);
								}
								n.parent();
							}
							n.parent();
						}
					}
				}
			}

		/*
			// mess with node search.
			findNodeVisitor findNode("Guided_Bullet PAT\nDYNAMIC");
			rootNode->accept(findNode);

			findCallbackNodeVisitor findCallbackNode("Guided_Bullet Callback");
			rootNode->accept(findCallbackNode);
			if (findCallbackNode.getNodeList().size() != 0)
			{
				cout << "found callback node: " << findCallbackNode.getNodeList()[0]->getName() << endl;
			}

			if (findNode.getNodeList().size() != 0)
			{
				cout << "found node: " << findNode.getNodeList()[0]->getName() << endl; 
			}
		*/


			void setRootNode(osg::Group &root, std::string runFile="")
			{
				// eventually, when we have multiple runs (visualization??.csv)
				// prompt between constructor and setting root node to pick the run to play back
				// that run = second argument, replaces input for bulletCallback (in this case)

				// presuming we get the sim node
				dsf::xml::xml xmlinput(filename);
					xmlinput.parse();

				parse(dsf::xml::xmlnode(*xmlinput.xmlRoot).search("vis"), root);

				// in the future we will set up a vector of camera options, instead of the 
				// bulletcallback option

			}
			baseCallback *getBulletCallback()
			{
				return bulletCallback;
			}

			// need not only this but corresponding labels
			// or set names on the callbacks (is that possible?) and look it up in mainwindow.
			// or a list of std::strings
			std::vector<cameraBase*>getCameras()
			{
				cout << "cameraVector: " << cameraVector.size() << endl;
				return cameraVector;
			}

			// temp - net - get a handle in mainwindow for updates (re-work later)
			baseCallback *bulletCallback;
		private:
			std::string filename;			// xml input filename
			std::vector<cameraBase*>cameraVector;

			NetClient * net;
			RenderThread * render;
		};
	}
}