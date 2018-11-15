#pragma once

#include "xml.h"

namespace dsf
{
	namespace xml
	{
		/// xml_reader takes an xml hierarchy and prints it to screen, useful for debugging.
		/// this should give the user a good inclination as to how to build xml configuration readers.
		/// This method uses straight nodes; a 'nicer' method uses xmlnodes.
		class xml_reader
		{
		public:
			xml_reader() {};

			/// Sets the XML hierarchy
			/// \param &XML XML Hierarchy
			void load_xml_hierarchy(xml &XML)
			{
				this->XML = &XML;
			}

			/// Print the system to screen.
			/// Calls a recursive function to traverse the entire graph.
			void print_system()
			{
				node n = *XML->xmlRoot;
				cout << "Root node: " << n.name << endl;
				j = 0;
				recurse(&n);
			};

			/// Recursive function used to print the system to screen.
			/// \param *n Current XML node under consideration.
			void recurse(node *n)
			{
				for (unsigned int i=0; i< n->child.size(); i++)
				{
					// tab node
					for (int k=0; k<=j; k++)
						cout << " ";

					// print node
					cout << "node: " << n->child[i]->name << endl;

					// print node's attributes
					for (unsigned int l=0; l<n->child[i]->attributes.size(); l++)
					{
						// tab
						for (int k=0; k<=j+1; k++)
							cout << " ";
						cout << n->child[i]->attributes[l].first << " " << n->child[i]->attributes[l].second << endl;
					}

					if(n->child[i]->child.size() != 0)
					{
						j = j + 1;
						recurse(n->child[i]);
					}
				}
				j = j - 1;
			};
		private:
			int j;			///< tab space counter.
			xml *XML;		///< XML Hierarchy.
		};
	}
}
