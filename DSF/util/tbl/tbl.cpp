#include "tbl.h"
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <cmath>

#include <sstream>
#include <string>
#include <vector>
using namespace std;

namespace dsf
{
	namespace util
	{
		/// Table custom constructor.
		/// \param fname is the filename containing the file.
		/// \param tabName is the header of the table to look for.
		Table::Table(std::string fname,std::string tabName)
				{
					tableName = tabName;
//					cout << " looking for " << tabName << " in " << fname << endl;
					//StreamReader sr = new StreamReader(@fname);	// need exception handling
					//String strLine;

					ifstream myfile (fname.c_str());
					if (myfile.is_open())
					{}
					else
					{
						cout << "error opening file " << fname << " looking for " << tabName << endl;
						char xx; cin >> xx;
					}

					string strLine;
					string line;
					while (getline(myfile,line))	// seek to line matching tabName
					{
						if (line.compare(tabName) == 0)
						{
							cout << "found: " << line << endl;
							break;
						}
					}
					// read next line, which is number of lines
					getline(myfile,line);

					// get the number of rows, instantiate table
					int numberOfLines = atoi(line.c_str());
//					cout << "number of lines: " << numberOfLines << endl;

					//table = new double[numberOfLines,2];
					// size table
					table = new double*[numberOfLines];
					for (int i=0; i <=numberOfLines-1; i++)
					{
						table[i] = new double[2];
					}

					min = 0;
					max = numberOfLines - 1;

					// skip the human readable header
					//sr.ReadLine();
					getline(myfile,line);

					for ( int i=0; i < numberOfLines; i++ )
					{
						getline(myfile,line);

						//strLine = sr.ReadLine();
						// you have one line, split it into each part and place into array
						//string[] values = strLine.Split('\t');

						// assuming a well-formed table of "value <delimeter, tab> value"
						string::size_type pos = line.find_first_of("\t", 0);
				double result;
				istringstream( line.substr(0,pos).c_str() ) >> result;
						table[i][0] = result;			//Convert.ToDouble( values[0] );
				istringstream( line.substr(pos+1,line.size()) ) >> result;
						table[i][1] = result;	//Convert.ToDouble( values[1] );

		//				table[i][0] = atof(line.substr(0,pos).c_str());			//Convert.ToDouble( values[0] );
		//				table[i][1] = atof(line.substr(pos+1,line.size()).c_str());	//Convert.ToDouble( values[1] );
					}
					myfile.close();
				}

		Table::Table(std::string csv_file, std::string x_col, std::string y_col, bool isCSV)
		{
			tableName = y_col;
			ifstream myfile(csv_file.c_str());
			if (!myfile.is_open())
			{
				cout << "Table: error opening CSV file " << csv_file << endl;
				table = new double*[1]; table[0] = new double[2]; table[0][0] = 0; table[0][1] = 0; min = 0; max = 0; return;
			}
			
			string line;
			if (!getline(myfile, line)) {
				table = new double*[1]; table[0] = new double[2]; table[0][0] = 0; table[0][1] = 0; min = 0; max = 0; return;
			}
			
			// Parse header
			int x_idx = -1, y_idx = -1;
			std::vector<string> headers;
			stringstream ss(line);
			string cell;
			while (getline(ss, cell, ','))
			{
				cell.erase(0, cell.find_first_not_of(" \r\n\t"));
				cell.erase(cell.find_last_not_of(" \r\n\t") + 1);
				headers.push_back(cell);
			}
			
			for (size_t i = 0; i < headers.size(); i++)
			{
				if (headers[i] == x_col) x_idx = i;
				if (headers[i] == y_col) y_idx = i;
			}
			
			if (x_idx == -1 || y_idx == -1)
			{
				cout << "Table CSV Error: could not find columns " << x_col << " or " << y_col << " in " << csv_file << endl;
				table = new double*[1]; table[0] = new double[2]; table[0][0] = 0; table[0][1] = 0; min = 0; max = 0; return;
			}
			
			// Read data
			std::vector<std::pair<double, double>> data;
			while (getline(myfile, line))
			{
				if (line.empty() || line[0] == '\r') continue;
				stringstream ss_row(line);
				string val;
				double x_val = 0, y_val = 0;
				int col_idx = 0;
				while (getline(ss_row, val, ','))
				{
					if (col_idx == x_idx) x_val = atof(val.c_str());
					if (col_idx == y_idx) y_val = atof(val.c_str());
					col_idx++;
				}
				data.push_back(std::make_pair(x_val, y_val));
			}
			myfile.close();
			
			int numberOfLines = data.size();
			if (numberOfLines == 0) {
				table = new double*[1]; table[0] = new double[2]; table[0][0] = 0; table[0][1] = 0; min = 0; max = 0; return;
			}
			
			table = new double*[numberOfLines];
			for (int i = 0; i < numberOfLines; i++)
			{
				table[i] = new double[2];
				table[i][0] = data[i].first;
				table[i][1] = data[i].second;
			}
			min = 0;
			max = numberOfLines - 1;
		}

		/// Table interpolation.
		/// \param x Value to interpolate for.
		double Table::interp(double x)
		{
			if (min == max) return table[min][1];
			if (x <= table[min][0]) return table[min][1];
			if (x >= table[max][0]) return table[max][1];
			return binarySearch(x, min, max);
		}

		/// Binary search function.
		/// \param val Value to interpolate for.
		/// \param left minimum size of the array
		/// \param right maximum size of the array
		/// left/right are redundant but the plan is to abstract binarySearch to a base class \n
		/// and have all table classes use the same binarySearch for optimal code resule and  \n
		/// less possibility for bugs / discrepancies.
		double Table::binarySearch(double val, int left, int right)
		{
			int mid;	// indexer
			while ( (left <= right)) // & left >= min & right <= max to bound table; may have to fix after loop
			{
				mid = (int)floor( (double)((right-left)/2 + left));
				if (val > table[mid][0] )
					left = mid + 1;
				else if (val < table[mid][0] )
					right = mid -1;
				else	// right on the money, val == table[mid][0]
					return table[mid][1];

				if (left == max)
					break;
				if (right == min)
					break;
			}

			if ( left == right && left == min )
				return table[0][1];
			else if ( left == right && right == max )
				return table[max-1][1];
			else
			{
				return (table[right][1] - table[left][1]) * ( (val - table[left][0])/(table[right][0]-table[left][0]) ) + table[left][1];
			}
		}
	}
}
