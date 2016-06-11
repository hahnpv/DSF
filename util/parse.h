#pragma once
#include <iostream>
#include <sstream>
#include <string>
using namespace std;

namespace dsf
{
	namespace util
	{
		/*			/// interesting
		template<typename T> T convertTo(const string& fromString) 
		{
			T toT;
			istringstream(fromString)>> toT;
			return toT;
		}
		*/
			/// A templated parsing class.
			/// \param str input string to be split.
			/// \param delims delimeters by which the string is split.
			/// TClass is the return type. There is no error checking.
		template< class TClass> std::vector<TClass> split( std::string str, std::string delims)
		{
		  using namespace std;
		  // Skip delims at beginning, find start of first token
		  string::size_type lastPos = str.find_first_not_of(delims, 0);
		  // Find next delimiter @ end of token
		  string::size_type pos     = str.find_first_of(delims, lastPos);

		  // output vector
		  vector< TClass> tokens;

		  while (string::npos != pos || string::npos != lastPos)
			{
				TClass result;
				istringstream is( str.substr(lastPos, pos - lastPos) );
				is >> result;
//2016			istringstream( str.substr(lastPos, pos - lastPos) ) >> result;

			  // Found a token, add it to the vector.
			  tokens.push_back( result );
			  // Skip delims.  Note the "not_of". this is beginning of token
			  lastPos = str.find_first_not_of(delims, pos);
			  // Find next delimiter at end of token.
			  pos     = str.find_first_of(delims, lastPos);
			}
			return tokens;
		}
	}
}