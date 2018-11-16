#pragma once

// output
// any class can register with output to output data to a common file
// CSV for now
//
#include <iostream>
#include <fstream>
#include <sstream> // stupid string stream

#include "block.h"
#include "../util/math/vec3.h"
#include "../util/math/mat3.h"
#include "../util/file/get_unique_file.h"

namespace dsf
{
	namespace sim 
	{
		class Output : public Block
		{
		public:
			Output(double _rate)
			{
				out = NULL;
				rate = _rate;
				rptRate = _rate;
				title.resize(2);
				units.resize(2);
			}
			void report()		// reporting function called by both init and rpt
			{
				// for now do in order added, doubles then vecs then mats

				*out << t();
				// doubles
				for (unsigned int i=0; i < doubles.size(); i++)
				{
					*out << ", " << *doubles[i];
				}

				// vectors
				for (unsigned int i=0; i < vectors.size(); i++)
				{
					*out << ", " << (*vectors[i]).x << ", " << (*vectors[i]).y << ", " << (*vectors[i]).z;
				}

				// matrices
				for (unsigned int i=0; i < matrices.size(); i++)
				{
					*out << ", " << *matrices[i];
				}
				*out << endl;
			};
			void open()
			{
				string filename = "output.csv";
				std::string file = dsf::util::get_unique_file(filename).filename;
				out = new ofstream(file.c_str(), ios::out);
				out->precision(10);		// places after the decimal
				out->width(10);			// digits to write
//THIS WORKS IN MSVC		out->setstate(ios::fixed);
				// print title and units.
				*out <<" Time ";
				for (unsigned int i=0; i < title.size(); i++)
				{
					for (unsigned int j=0; j < title[i].size(); j++)
					{
						if ( i == 1)	// vector notation, 3 columns
						{
							*out << ", " << title[i][j] << " (x) ";
							*out << ", " << title[i][j] << " (y) ";
							*out << ", " << title[i][j] << " (z) ";
						}
						else
							*out << ", " <<  title[i][j];
					}
				}
				*out << endl;

				*out << " [s] ";
				for (unsigned int i=0; i < units.size(); i++)
				{
					for (unsigned int j=0; j < title[i].size(); j++)
					{
						if ( i == 1)	// vector notation, 3 columns
						{
							*out << ", " << units[i][j];
							*out << ", " <<  units[i][j];
							*out << ", " <<  units[i][j];
						}
						else
							*out << ", " <<  units[i][j];
					}
				}
				*out << endl;
			};

			void rpt()
			{
				if ( out == NULL)
					open();

				report();
			};

			void finalize()
			{
				out->close();
			};

			// accessors with title and units
			void add(double &d, string title, string units)
			{
				doubles.push_back(&d);
				this->title[0].push_back(title);
				this->units[0].push_back(units);
			}
			void add(dsf::util::Vec3 &v, string title, string units)
			{
				vectors.push_back(&v);

				if (title.size() < 1)
				{ }
				this->title[1].push_back(title);
				this->units[1].push_back(units);
			}
			void add(dsf::util::Mat3 &m, std::string title, std::string units)
			{
				matrices.push_back(&m);
				this->title[2].push_back(title);
				this->units[2].push_back(units);
			}

		private:
			double rate;
			vector< vector< std::string> >title;
			vector< vector< std::string> >units;
			vector< double *>doubles;
			vector< dsf::util::Vec3 *>vectors;
			vector< dsf::util::Mat3 *>matrices;
			ofstream *out;
		};
	}
}
