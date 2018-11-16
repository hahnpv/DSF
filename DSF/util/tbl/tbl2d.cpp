#include "tbl2d.h"
#include <iostream>
#include <fstream>
#include <cmath>
#include "../parse.h"
using namespace std;

namespace dsf
{
	namespace util
	{
		/// Table2d custom constructor
		/// \param fname Filename of the 2D table
		/// A filename can only contain a single 2D table.
		Table2d::Table2d(std::string fname)
		{
//			cout << "reading all tables out of " << fname << endl;
			// split by " " but make easy to change

			ifstream myfile (fname.c_str());
			if (myfile.is_open())
			{}
			else
			{
				cout << "error opening file " << fname << endl;
				char xx; cin >> xx;
			}

			string strLine;
			string line;

			// skip table seek, it is 1 table

			// read first line which is the header - "n=0"
			getline(myfile,line);

			// read the next line - header, names of columns. Throw for now but eventually, analyze
			getline(myfile,line);

			while( !myfile.eof() )
			{
				getline(myfile,line);

						// now we have n tokens, split by ' ' and throw into std::vector< std::vector< double>>table;
				std::vector< double> result = dsf::util::split< double>(line,", \t");
				if (result.size() == 0)
				{}
				else
					table.push_back( result);
			}
			myfile.close();
		}


		/// Table interpolation.
		/// \param x Value to interpolate for.
		/// \param i Column to return.
		double Table2d::interp(double x, int i)
		{
			return binarySearch(x, i, 0, table.size()-2);
		}

		/// Table interpolation.
		/// \param x Value to interpolate for.
		/// This method returns a vector containing the row of solutions at interpolation value x.
		std::vector< double> Table2d::interp(double x)
		{
			std::vector< double> result;
			for (unsigned int i=0; i<table[0].size(); i++)
			{
				int mid = 0;	// indexer
				int left = 0;
				int right = table.size()-2;
				bool push_back = false;

				while ( left <= right)		// changed criteria from right - left > 1
				{
					mid = (int)floor( (double)((right-left)/2 + left));
					if (x > table[mid][0] )
						left = mid + 1;
					else if (x < table[mid][0] )
						right = mid -1;
					else
					{
						result.push_back( table[mid][i]);
						push_back = true;
						break;
					}
				}
				if (!push_back)
				{
					result.push_back( interp(x,i,left,right));
				}
			}
			return result;
		}

		/// Second half of the binary search function.
		/// Eventually this and binarySearch and the binarySearch method in \n
		/// Table will be placed in a parent class to minimize discrepancies.
		double Table2d::interp(double val, int i, int left, int right)
		{
			if      ( left == right && left == 0 )			// 0 = min
				return table[0][i];
			else if ( left == right && right == table.size() )	// table.size() = max 
				return table[table.size()-1][i];				// same
			else
				return (table[right][i] - table[left][i]) * ( (val - table[left][0])/(table[right][0]-table[left][0]) ) + table[left][i];
		}

		/// First half of the binary search function.
		/// Eventually this and interp(val,i,left,right) and the binarySearch method in \n
		/// Table will be placed in a parent class to minimize discrepancies.
		double Table2d::binarySearch(double val, int i, int left, int right) // will need to spec a column
		{
			int mid;	// indexer
			while ( left <= right)		// changed criteria from right - left > 1
			{
				mid = (int)floor( (double)((right-left)/2 + left));
				if (val > table[mid][0] )
					left = mid + 1;
				else if (val < table[mid][0] )
					right = mid -1;
				else
					return table[mid][i];
			}
			return interp(val, i, left, right);
		}
	}
}
