#pragma once

// monitor for visual playback, single body atm (can vector)
// any class can register with output to output data to a common file
// CSV for now 
// 
//	Thought for now -> don't even use position struct just snag xyz and euler
//	Maybe later we can come up with a unified 6DOF struct for messaging/data
//
//	incomplete
//
//	This is very specific data for a single vehicle. Not sure if I like it.
//	Think about how to deal with
//		- multiple vehicles (multiple files I'd presume ... or multiple columns)
//		- staging. **that** will be difficult. Will probably need to stop scene, 
//			delete existing node, create 2 nodes and start from there over again.
//
//
#include <iostream>
#include <fstream>
#include <sstream> // stupid string stream
using namespace std;

#include "../sim/Block.h"
#include "../util/math/Vec3.h"
#include "../util/file/get_unique_file.h"

namespace dsf
{
	namespace vis
	{
			/// Visualization monitor, monitors the block containing position and orientation and 
			/// dumps it to a file for playback.
			/// Needs to be expanded to save othe pertinent data, data for multiple actors, etc.
			/// Similar in nature to output
		class VisMonitor : public dsf::sim::Block
		{
		public:
			VisMonitor()
			{
				out = NULL;
				rate = 0.001;
			}

				/// Reporting function, called by init() and rpt().
				/// This function writes a single data point to the output stream.
			void report()
			{
				*out << t();
				*out << ", " << (*xyz).x << ", " << (*xyz).y << ", " << (*xyz).z;
				*out << ", " << (*euler).x << ", " << (*euler).y << ", " << (*euler).z;
				*out << endl;
			};
				
				/// Opens a file stream.
			void open()
			{
				cout << "in monitor::open" << endl;
				string filename = "visualize.csv";
				std::string file = dsf::util::get_unique_file(filename).filename;
				out = new ofstream(file.c_str(), ios::out);
				cout << "done" << endl;
				out->precision(4);			// places after the decimal
				out->width(10);				// digits to write
				out->setf(ios::fixed);		// set the output to fixed, ie, not floating point
				out->setf(ios::showpoint);	// show the decimal point, ie, do not truncate output under any circumstance

				// print title
				*out <<" Time, ";
				*out << "Position (x), Position (y), Position(z), ";
				*out << "Orientation (x), Orientation (y), Orientation (z)";
				*out << endl;

				// print units
				*out <<" [seconds], ";
				*out << "[m], [m], [m], ";
				*out << "[rad], [rad], [rad]";
				*out << endl;
			};

				/// Overloaded report function
			void rpt()
			{
				if ( out == NULL)
					open();

				if ( sample(rate) || t() == 0 )
				{
					report();
				}
			};

				/// Overloaded finalize function
			void finalize()
			{
				report();
				out->close(); 
			};

				/// Position reference : set the position vector to monitor
			void position(dsf::util::Vec3 &v)
			{
				xyz = &v;
			}
				
				/// Orientation reference : set the orientation vector to monitor
			void orientation(dsf::util::Vec3 &v)
			{
				euler = &v;
			}

		private:
			double rate;
			ofstream *out;
			dsf::util::Vec3 *xyz;
			dsf::util::Vec3 *euler;
		};
	}
}