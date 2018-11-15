#pragma once
#include <string>
#include <vector>
    //	adapting to a 2D table

namespace dsf
{
	namespace util
	{
		// 1D multiple column table class
		// can make truly 2d by adding a second interpolation vector interp method, not hard ...
		class Table2d
		{
		public:
			Table2d(std::string fname);
			double interp(double x, int i);
			std::vector< double> interp(double x);		// interp all columns at once
		//	std::vector< double> tokenize(const std::string & str, const std::string & delims=", \t");
		private:
			double binarySearch(double val, int i, int left, int right);		// binary search
			double interp(double val, int i, int left, int right);				// interp given all binary search data
			
			// need some way of matching a key to a location, pair?

			std::vector< std::vector< double> >table;	// table out of vectors you got a problem with that? :)
														// means we dont have to worry about validating size, etc.
		};
	}
}
