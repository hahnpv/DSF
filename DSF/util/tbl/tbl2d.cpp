#include "tbl2d.h"
#include "../config_errors.h"
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
			if (!myfile.is_open())
			{
				cerr << "Table2d: error opening file " << fname << endl;
				dsf::util::config_errors().push_back("Table2d: error opening file " + fname);
				return;		// leaves an empty table; interp() returns 0 / empty
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


		/// Multi-column 1D interpolation.
		/// \param x Independent-variable value to interpolate for (column 0).
		/// \param i Column to return.
		/// Clamps to the table endpoints for out-of-range x (matching Table), so a
		/// query below the first breakpoint no longer reads table[-1].
		double Table2d::interp(double x, int i)
		{
			int n = (int)table.size();
			if (n == 0) return 0.0;
			if (n == 1) return table[0][i];

			// Clamp out-of-range queries to the endpoints.
			if (x <= table[0][0])   return table[0][i];
			if (x >= table[n-1][0]) return table[n-1][i];

			// Find bracket [lo, lo+1] with table[lo][0] <= x < table[lo+1][0].
			int lo = 0, hi = n - 1;
			while (hi - lo > 1)
			{
				int mid = lo + (hi - lo) / 2;
				if (x < table[mid][0])
					hi = mid;
				else
					lo = mid;
			}

			double x0 = table[lo][0], x1 = table[hi][0];
			if (x1 == x0) return table[lo][i];	// duplicate breakpoint guard
			return table[lo][i] + (table[hi][i] - table[lo][i]) * (x - x0) / (x1 - x0);
		}

		/// Multi-column 1D interpolation returning every column at x.
		std::vector< double> Table2d::interp(double x)
		{
			std::vector< double> result;
			if (table.empty()) return result;
			int ncol = (int)table[0].size();
			for (int i = 0; i < ncol; i++)
				result.push_back(interp(x, i));
			return result;
		}
	}
}

// ---- New bilinear interpolation support ----

namespace dsf
{
	namespace util
	{
		/// Construct from breakpoints and data grid (bilinear 2D mode)
		Table2d::Table2d(const std::vector<double>& rows,
		                 const std::vector<double>& cols,
		                 const std::vector<std::vector<double>>& data)
			: row_breaks(rows), col_breaks(cols), grid(data)
		{
		}

		/// Binary search for bracket index: returns j such that breaks[j] <= val < breaks[j+1]
		/// Clamps to valid range [0, n-2].
		int Table2d::findBracket(const std::vector<double>& breaks, double val)
		{
			int n = (int)breaks.size();
			if (n < 2) return 0;

			// Clamp to table bounds
			if (val <= breaks[0]) return 0;
			if (val >= breaks[n-1]) return n - 2;

			// Binary search
			int lo = 0, hi = n - 2;
			while (lo < hi)
			{
				int mid = (lo + hi) / 2;
				if (val < breaks[mid])
					hi = mid - 1;
				else if (val >= breaks[mid + 1])
					lo = mid + 1;
				else
					return mid;  // breaks[mid] <= val < breaks[mid+1]
			}
			return lo;
		}

		/// True 2D bilinear interpolation: f(row_val, col_val)
		///
		/// Standard bilinear interpolation over the 4 surrounding grid points:
		///   f(r,c) = (1-t)(1-u)*f00 + t*(1-u)*f10 + (1-t)*u*f01 + t*u*f11
		/// where t and u are the fractional positions within the bracket cell.
		double Table2d::interp(double row_val, double col_val)
		{
			// Find bracket indices
			int ri = findBracket(row_breaks, row_val);
			int ci = findBracket(col_breaks, col_val);

			// Compute fractional positions within the cell
			double dr = row_breaks[ri+1] - row_breaks[ri];
			double dc = col_breaks[ci+1] - col_breaks[ci];

			double t = (dr > 0.0) ? (row_val - row_breaks[ri]) / dr : 0.0;
			double u = (dc > 0.0) ? (col_val - col_breaks[ci]) / dc : 0.0;

			// Clamp fractions (for extrapolation protection)
			if (t < 0.0) t = 0.0; if (t > 1.0) t = 1.0;
			if (u < 0.0) u = 0.0; if (u > 1.0) u = 1.0;

			// Four corners
			double f00 = grid[ri  ][ci  ];
			double f10 = grid[ri+1][ci  ];
			double f01 = grid[ri  ][ci+1];
			double f11 = grid[ri+1][ci+1];

			// Bilinear formula
			return (1.0 - t) * (1.0 - u) * f00
			     + t         * (1.0 - u) * f10
			     + (1.0 - t) * u         * f01
			     + t         * u         * f11;
		}
	}
}

