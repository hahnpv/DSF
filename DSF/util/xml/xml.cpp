#include "xml.h"
#include "../parse.h"	// string splitter

using namespace std;
using namespace dsf::util;

namespace dsf
{
	namespace xml
	{
		/// Parse the xml structure.
		/// Parse calls a recursive function to traverse the input file.
		void xml::parse()
		{
			cout << "in xml::parse()" << endl;
			xmlRoot = new node;
			// recursively parse a file
			cout << "filename: " << filename << endl;
			file = new ifstream(filename.c_str(),ios::in);
			if (file->is_open())
			{
//				cout << "file open " << filename << endl;
			}
			else
			{
				cout << filename << endl;
				cout << "error opening file (xml::parse())" << endl; // filename << endl;
				cin.get();
				return;
			}
			xmlRoot->name = "xmlRoot";

			parentNode = xmlRoot;	// start at the root of the xml doc

			string line;
			while ( !file->eof() )
			{
				getline(*file, line);
				if (line.size() != 0)					// Ignore blank lines in the file
					recurse(line, true);
			}
			file->close();
		}

		/// Recursive function for traversing and xml file and storing it as a graph of nodes.
		/// \param line String containing the current line.
		/// \param state State represents whether the end tag has been found.
		bool xml::recurse(std::string line, bool state)
		{
				// ok now the problem is doing it :)

				// types of xml nodes
				// 1. <blah>
				// 2. </blah>
				// 3. <blah attr="" attr2="" />
				// 4. <blah attr="" attr2=""> </blah>
				// 5. <blah>arg</blah> 

				// 1. parse tokens: leading < attaches to first key. Trailing > with Slash or alone.
				// lone ">" is meaningless but should never occur		
				//	-> Slash however is meaningful.
				//	-> recycle string split function from table in simulation.
				vector< string>tokens = split< string>( line," =\"\t");

				// Case Two: match a closing tag
				string closingStatement = "</" + parentNode->name + ">";		// won't match right yet
				cout << "name/closing statement check: " << tokens[0] << "\t" << closingStatement << endl;
				if ( tokens.size() == 1 && tokens[0] == closingStatement)
				{
//					cout << "CLOSING TOKEN MATCH" << endl;
					// break level of recursion (if necessary ... ) but I think just changing parent ref is enough

					// need to move parent up one ... guess parentNode needs a ref to its parent?
					parentNode = parentNode->parent;
					return false;
				}

					// Case Three: we have a single line with no closing tag
				else if( tokens[tokens.size() - 1] == "/>")
				{
					parentNode->child.push_back( new node);

						// set parent node reference
					parentNode->child[parentNode->child.size()-1]->parent = parentNode;

						// set name (need to string leading '<')
					string name = tokens[0].substr(1,tokens[0].size()-1);
					cout << "giving parent node the name: " << name << endl;
					parentNode->child[parentNode->child.size()-1]->name = name;

						// set attributes
					for (unsigned int i=1; i < tokens.size()-1; i+=2)
					{
						cout << "adding pair of attributes: " << tokens[i] << "\t" << tokens[i+1] << endl;
						parentNode->child[parentNode->child.size()-1]->attributes.push_back( pair<string,string>(tokens[i],tokens[i+1]));
					}
					return true;
				}

					// Case One: leading tag, no attributes Recurse tree until we find mating tag.
					// need to change parent node to current node
					// **or** a leading tag with attributes (although attributes are NOT stored yet!

					//
					//	ultimately we want to be able to <node>arg arg arg</node>
					//	right now this doesn't get filtered in here ... see if we 
					//	can add an aditional matching criteria. For example, if <node>.insert(/,2) == </node>
					//  or after all if/elses, strip <,/,> and if 0 = tokens.size(), then we have a match.
					//	right now a comma-delimited thing falls in here as tokens.size() == 1
				else if ( tokens.size() == 1 || tokens[tokens.size()-1] == ">")
				{
					// special case: if we have a <node>arg</node>, it will get filtered here
					// check for it by searching line for a "</", which would otherwise not
					// get through this filter
					if (line.find("</") != string::npos)
					{
						cout << "special node: " << line << endl;
						// find and push back the attribute
						vector<string> arg = split< string>( line,"</>=\"\t");

						// write attributes to parentNode.
						// all get the label they are encapsulated by

						// scratch that ... make it 1 line, that way vecs/mats can be space delimited
						std::string attribute = arg[1];
						for (unsigned int i=2; i<arg.size()-1; i++)
						{
							attribute += " " + arg[i];
						}
							parentNode->attributes.push_back( pair<string,string>(arg[0],attribute));
//							cout << "adding pair: " << arg[0] << " " << attribute << endl;
					}
					else
					{
						parentNode->child.push_back( new node);

						// set parent node reference
						parentNode->child[parentNode->child.size()-1]->parent = parentNode;
						// set attributes, etc.

							// set name (need to string leading '<' and trailing '>')
						string name;
						if (tokens.size() == 1)
							name = tokens[0].substr(1,tokens[0].size()-2);
						else
							name = tokens[0].substr(1,tokens[0].size()-1);
//						cout << "giving parent node the name: " << name << endl;
						parentNode->child[parentNode->child.size()-1]->name = name;

							// set attributes (if any)
						if (tokens.size() != 1)
							for (unsigned int i=1; i < tokens.size()-1; i+=2)
							{
//								cout << "adding pair of attributes: " << tokens[i] << "\t" << tokens[i+1] << endl;
								parentNode->child[parentNode->child.size()-1]->attributes.push_back( pair<string,string>(tokens[i],tokens[i+1]));
							}


						parentNode = parentNode->child[parentNode->child.size()-1];
							// children
						cout << "PARENT NODE changed to " << parentNode->name;
						while (state)
						{
							getline(*file, line);
							state = recurse(line, true);
						}
					}
				}
				return true;
		}
	}
}
