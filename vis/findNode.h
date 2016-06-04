#pragma once

#include <osg/NodeVisitor>
#include <osg/Node>
	// this looks at nodes but not callbacks
	// need to mod 'apply'
	// need to clean.
namespace dsf
{
	namespace vis
	{

		/// findNodeVisitor finds nodes in the scene graph by matching node names.
		class findNodeVisitor : public osg::NodeVisitor 
		{
		public: 
				/// Default constructor, not very useful.
			findNodeVisitor(): osg::NodeVisitor(TRAVERSE_ALL_CHILDREN), searchForName()  {};

				/// Constructor that accepts a string to search for
			findNodeVisitor(const std::string &searchName)  : 
										   osg::NodeVisitor(TRAVERSE_ALL_CHILDREN), 
											   searchForName(searchName) {};

			/// Apply method compares our string with all node names and adds matches to
			/// a list
			virtual void apply(osg::Node &searchNode)
		   { 
			 if (searchNode.getName() == searchForName)
			{
				  foundNodeList.push_back(&searchNode);
			}
		   traverse(searchNode); 
		} ;

			/// Set the searchForName to user-defined string
		   void setNameToFind(const std::string &searchName)
		   { 
				searchForName = searchName; 
				foundNodeList.clear(); 
			} ;

//		   typedef std::vector<osg::Node*> nodeListType; 

		   std::vector<osg::Node*>& getNodeList() { return foundNodeList; }

		private: 

		   std::string searchForName; 
		   std::vector<osg::Node*> foundNodeList; 

		}; 
	}
}