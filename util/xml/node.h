#pragma once
#include <vector>

namespace dsf
{
	namespace xml
	{
		/// node encapsulates all the data of a single xml node.
		class node
		{
		public:
			std::string name;				///< Node name
			node *parent;					///< parent of the node.
			std::vector< node *>child;		///< children of the node.
			std::vector< std::pair< std::string,std::string> > attributes;	///< vector of key/attribute pairs.
			std::string value;		///< value if <name>value</name> structure.					
		};
	}
}
