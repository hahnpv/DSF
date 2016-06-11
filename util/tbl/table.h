#ifndef TABLE_H
#define TABLE_H
#include <string>
#include <map>
class Table		// simple 1D table for now
{
public:
	Table(std::string fname, std::string tabName);	// file name, name of table
	~Table() {};

	double interp(double x) { return binarySearch(x, min, max); };
	double binarySearch(double val, int left, int right);
	int min;
	int max;
	double **table;
};
#endif
