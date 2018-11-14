#pragma once
#include <string>
	// i have no idea if the following comment applies anymore
	//
	//	having some issues with small (2-3) element tables, possibly with sharp number jumps
	//
    //  and a xml version :P have a base class table, then derive this class and xml class
    //
    //

// 1D table class
namespace dsf
{
	namespace util
	{
		class Table
		{
		public:
			Table() {};
			Table(std::string fname, std::string tabName);
			double interp(double x);
			double operator()(double x)
			{
				return interp( x);
			};
		private:
			double binarySearch(double val, int left, int right);
			std::string tableName;
			int min;
			int max;
			double **table;		// need to dimension in the constructor
		};
	}
}