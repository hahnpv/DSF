#pragma once

#include <osg/NodeVisitor>
#include <osg/Node>

namespace dsf
{
	namespace vis
	{
			/// traverse a scene graph, looking at their callbacks
			/// (utilize, for instance, to find all cameras)
			/// returns vector containing matches.
		class findCallbackNodeVisitor : public osg::NodeVisitor { 
		public: 
				/// Default constructor.
			findCallbackNodeVisitor(): osg::NodeVisitor(TRAVERSE_ALL_CHILDREN), searchForName()  {};

				/// Overloaded constructor for a desired search string.
			findCallbackNodeVisitor(const std::string &searchName)  : 
										   osg::NodeVisitor(TRAVERSE_ALL_CHILDREN), 
											   searchForName(searchName) {};

					/// Apply method compares internal string with names of the nodes in the scene graph
					/// Matches are pushed back onto a result vector
			virtual void apply(osg::Node &searchNode)
			{   
				if (searchNode.getUpdateCallback())
				{	
				   if (searchNode.getUpdateCallback()->getName() == searchForName)
					{
					   foundNodeList.push_back(searchNode.getUpdateCallback());
					}
			}
		   traverse(searchNode); 
		} ;

			/// Set internal string
		   void setNameToFind(const std::string &searchName)
		   { 
			searchForName = searchName; 
		   foundNodeList.clear(); 
		} ;

		   std::vector<osg::NodeCallback *>& getNodeList() { return foundNodeList; }

		private: 
		   std::string searchForName; 
		   std::vector<osg::NodeCallback *>foundNodeList;
		}; 
	}
}