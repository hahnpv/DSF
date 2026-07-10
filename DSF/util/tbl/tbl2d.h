/**
 * @file tbl2d.h
 * @brief Legacy 2D interpolation table (bilinear + multi-column).
 * @deprecated Use TableND from tablend.h instead.
 */
#pragma once
#include <string>
#include <vector>

namespace dsf
{
	namespace util
	{
		/// Multi-column and true 2D bilinear interpolation table.
		///
		/// Supports two modes of operation:
		///   1. Multi-column 1D: interp(x, col) or interp(x) for all columns
		///   2. True bilinear 2D: interp(row_val, col_val) with two independent variables
		///
		/// For bilinear mode, the table layout is:
		///       col_break[0]  col_break[1]  ...  col_break[nc-1]
		///   row_break[0]   data[0][0]     data[0][1]    ...  data[0][nc-1]
		///   row_break[1]   data[1][0]     data[1][1]    ...  data[1][nc-1]
		///   ...
		///   row_break[nr-1] data[nr-1][0]  ...              data[nr-1][nc-1]
		///
		class Table2d
		{
		public:
			Table2d() {}

			/// Construct from a text file (multi-column 1D mode)
			Table2d(std::string fname);

			/// Construct from breakpoints and data grid (bilinear 2D mode)
			/// @param row_breaks  Row breakpoint values (e.g. alpha)
			/// @param col_breaks  Column breakpoint values (e.g. delta_ht)
			/// @param data        nr x nc data grid
			Table2d(const std::vector<double>& row_breaks,
			        const std::vector<double>& col_breaks,
			        const std::vector<std::vector<double>>& data);

			/// 1D interpolation: return column i at independent variable x
			double interp(double x, int i);

			/// 1D interpolation: return all columns at independent variable x
			std::vector<double> interp(double x);

			/// True 2D bilinear interpolation: f(row_val, col_val)
			/// Uses row_breaks and col_breaks for the two independent variables.
			double interp(double row_val, double col_val);

			/// Number of rows in the table
			int rows() const { return (int)table.size(); }

			/// Number of columns in the table (including independent variable column)
			int cols() const { return table.empty() ? 0 : (int)table[0].size(); }

		private:
			/// Find bracket index: returns j such that breaks[j] <= val < breaks[j+1]
			/// Clamps to [0, n-2] for out-of-range values.
			static int findBracket(const std::vector<double>& breaks, double val);

			std::vector<std::vector<double>> table;

			// Bilinear mode breakpoints (empty for multi-column 1D mode)
			std::vector<double> row_breaks;
			std::vector<double> col_breaks;
			std::vector<std::vector<double>> grid; // nr x nc data values
		};
	}
}
