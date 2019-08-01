#pragma once
#include <iostream>
#include <fstream>
#include <sstream> // stupid string stream

namespace dsf
{
	namespace util
	{
		/// Obtain a unique file name.
		/// This class takes a file name, string searches for the last dot, and inserts 
		/// numbers until a unique filename is found.
		class get_unique_file
		{
		public:
			/// Custom constructor.
			/// \param filename Filename to use.
			get_unique_file(std::string filename) 
			{
				ofstream out(filename.c_str(), ios::in);

				int i = 0;
				while (out.is_open())
				{
					out.close();

					int offset = filename.find_last_of('.');
					stringstream s;
					string str;
					s << i;
					s >> str;

					int lastsize = 1;
					if (i - 1 >= 10)
						lastsize = 2;

					if ( i == 0)
						filename.insert(offset,str);
					else
					{
						filename.erase(offset-lastsize,lastsize);
						filename.insert(offset-lastsize,str);
					}
					out.open(filename.c_str(), ios::in);
					i++;
				}
				out.close();		// unique file name found
				this->filename = filename;
			};
			std::string filename;
		};
	}
}
