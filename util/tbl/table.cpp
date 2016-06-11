#include "table.h"
#include <fstream>
#include <iostream>
#include <cmath>
using namespace std;
Table::Table(string fname, string tabName)
{
	string input;
	ifstream file(fname.c_str());

	while ( getline(file, input, '\n') && input != tabName)	// seek to table name
	{
	}
	double numRows, numColumns;
	numColumns = 2;					// only 2 column tables for now

	getline(file, input, '\n');			// next line is number of rows
	numRows = (int)atof(input.c_str());
	table = new double*[(int)numRows];		// allocate a table
	for (int i=0; i<numRows; i++)			// rows
		table[i] = new double[(int)numColumns];	// columns	

	getline(file, input, '\n');			// throw away units line

	for (int i=0; i<numRows; i++)			// load data into table
	{
		getline(file, input, '\n');
		size_t len = input.find_first_of('\t');		// tab-delimited tables
		table[i][0] = atof(input.substr(0,len).c_str());
		table[i][1] = atof(input.substr(len,input.length()).c_str());
	}
	min = 0;
	max = numRows - 1;
}

double Table::binarySearch(double val, int left, int right)
{
	int mid;		// indexer
	while ( right - left > 1)
		{
			mid = (int)floor( (right-left)/2 + left);
			if (val > table[mid][0] )
				left = mid + 1;
			else if (val < table[mid][0] )
				right = mid - 1;
		}
		if      ( left == right && left == min )
			return table[0][1];
		else if ( left == right && right == max ) 
			return table[max][1];
		else
			return (table[right][1] - table[left][1]) 
			       * ( (val - table[left][0])/(table[right][0]-table[left][0]) ) + table[left][1];
}
