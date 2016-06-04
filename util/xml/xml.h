#pragma once

#include <string>

#include <iostream>
#include <fstream>

#include "node.h"
#include "xmlnode.h"

	// very simple XML parser
	// take XML file and dump it to a std::vector of nodes
	// then develop readers for each situation
	// need search functionality here or somewhere
namespace dsf
{
	namespace xml
	{
		class xml
		{
		public:
			xml(std::string filename) 
			{
				this->filename = filename;
			};
			void parse();
			bool recurse(std::string line, bool state);		// recursive parsing function
			node *xmlRoot;						///< xml document in nodal form.
		private:
			node *parentNode;					///< working parent node during parse.
			std::string filename;				///< Filename of the xml file.
			std::ifstream *file;				///< Input file stream.
		};
	}
}