/**
 * @file parse.h
 * @brief Templated string tokenizer and parser.
 *
 * Provides a split() function that tokenizes a delimited string and
 * converts each token to the specified type via `operator>>`.
 */
#pragma once

#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
using namespace std;

namespace dsf
{
	namespace util
	{
		/**
		 * @brief Split a delimited string into typed tokens.
		 * @tparam TClass Return type for each token (must support `operator>>`).
		 * @param str    Input string to tokenize.
		 * @param delims Delimiter characters.
		 * @return Vector of parsed tokens.
		 */
		template< class TClass> std::vector<TClass> split( std::string str, std::string delims)
		{
		  using namespace std;

		  // Skip delims at beginning, find start of first token
		  string::size_type lastPos = str.find_first_not_of(delims, 0);
		  // Find next delimiter @ end of token
		  string::size_type pos     = str.find_first_of(delims, lastPos);

		  // output vector
		  vector< TClass> tokens;
/*
		  string s;
		  while(str >> std::quoted(s))
		  {
			  tokens.push_back(s)
		  }
		  return tokens;
*/

		  while (string::npos != pos || string::npos != lastPos)
			{
				TClass result;
//TODO this can be easier: istringinstrem is; is << str; is >> token[0] >> token[1] ... etc
//THIS IS VALID IN MSVC	istringstream( str.substr(lastPos, pos - lastPos) ) >> result;
			istringstream is( str.substr(lastPos, pos - lastPos) );
			is >> result;

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
