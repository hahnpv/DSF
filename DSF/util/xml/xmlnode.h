#pragma once

#include "../math/vec3.h"
#include "../math/mat3.h"
#include "../parse.h"	// string splitter

	// don't like the name but brain was crapping out
	// this class hold pointer to a node. can then search or move up to parent.
	// move search function to here, and create a parent function here.
	// will work here (versus in the actual node in the graph) since we won't be 
	// changing parent/child relationships just the node under observation to this class.

using namespace dsf::util;

namespace dsf
{
	namespace xml
	{
		/// xmlnode is a useful container for xml nodes.
		/// xmlnode provides functionality to search for child nodes and convert
		/// attributes into different types.
		class xmlnode
		{
		public:

			/// Custom constructor.
			/// \param &node The node to start with.
			xmlnode( node &node)
			{
				this->node = &node;
			}

			/// Moves up a node to the parent.
			// can't chain multiple... ?
			xmlnode parent()
			{
				return *(node = node->parent);
			}

			/// Switch to a child node.
			/// \param i the count of the child node.
			xmlnode child(int i)
			{
				return *(node = node->child[i]);
			}


			/// Return the number of child nodes.
			unsigned int numchild()
			{
				return node->child.size();
			}

			/// Parameter search function.
			/// returns true if the attribute is found.
			/// \param str Search string.
			bool findAttr(std::string str)
			{
				if ( node->attributes.size() > 0)
				{
					for (unsigned int i=0; i<node->attributes.size(); i++)
					{
						if (node->attributes[i].first.compare(str) == 0)
						{
							return true;
						}
					}
				}
				return false;
			}

			/// Return an attribute as a string
			/// If an attribute is found that matches the input string, then the 
			/// matching parameter will be returned as a string.
			/// \param str Search string.
			std::string attrAsString(std::string str)
			{
				if ( node->attributes.size() > 0)
				{
					for (unsigned int i=0; i<node->attributes.size(); i++)
					{
						cout << node->attributes[i].first << " " << str << endl;
						if (node->attributes[i].first.compare(str) == 0)
						{
							return node->attributes[i].second.c_str();
						}
					}
				}
				return "";
			}

			/// Return an attribute as a boolean
			/// \param str Search string.
			bool attrAsBool(std::string str)
			{
				std::string source = attrAsString(str);
				if ( source.compare("true") == 0)
					return true;
				else
					return false;
			}

			/// Return an attribute as a Vec3
			/// If an attribute is found that matches the input string, then the 
			/// matching parameter will be returned as a string.
			/// \param str Search string.
			dsf::util::Vec3 attrAsVec3(std::string str)
			{
				std::string source = attrAsString(str);
				std::vector< double> v = dsf::util::split< double>(source,",");
				return dsf::util::Vec3(v[0], v[1], v[2]);
			}

			/// Return an attribute as a Mat3
			/// If an attribute is found that matches the input string, then the 
			/// matching parameter will be returned as a string.
			/// \param str Search string.
			dsf::util::Mat3 attrAsMat3(std::string str)
			{
				std::string source = attrAsString(str);
				std::vector< double> m = dsf::util::split< double>(source,",");
				return dsf::util::Mat3(m[0],m[1],m[2],m[3],m[4],m[5],m[6],m[7],m[8]);
			}

			/// Return an attribute as a double
			/// If an attribute is found that matches the input string, then the 
			/// matching parameter will be returned as a string.
			/// \param str Search string.
			double attrAsDouble(std::string str)
			{
				std::string source = attrAsString(str);
				double result;
				istringstream( source ) >> result;
				return result;
			}


			/// Searches for a child node by name. 
			/// Returns true if found. This can be useful to encapsulate a child search
			/// e.g., if (findChild("name")) { // use the child } else { // no child found }
			bool findChild( std::string str)
			{
				for (unsigned int i=0; i<node->child.size(); i++)
				{
					if (node->child[i]->name.compare(str) == 0)
					{
						return true;
					}
				}
				return false;
			};

			/// Searches for a child node, returning the child node if found.
			/// Otherwise, it returns the *this pointer.
			xmlnode search(std::string str)
			{
				for (unsigned int i = 0; i < node->child.size(); i++)
				{
					if (node->child[i]->name.compare(str) == 0)
					{
//						cout << "returning " << node->child[i]->name << endl;
						return *(node = node->child[i]);
					}
				}
				// 2016 - if node is str return it!
				if (node->name.compare(str) == 0)
				{
					return *node;
				}
				cout << "no match found: " << str << endl;
				return *this;
			};


			/// Return a vector of children for direct iteration.
			std::vector< node*>children()
			{
				return node->child;
			}

			/// Return the name of the current node.
			std::string name()
			{
				return node->name;
			}

		private:
			node *node;
		};
	}
}
