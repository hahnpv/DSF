/**
 * @file output.h
 * @brief CSV output handler for simulation telemetry.
 * 
 * Provides automatic CSV file generation with column headers for doubles,
 * Vec3, and Mat3 state variables. Supports unit conversion factors.
 */
#pragma once

#include <iostream>
#include <fstream>
#include <sstream>

#include "block.h"
#include "../util/math/vec3.h"
#include "../util/math/mat3.h"
#include "../util/file/get_unique_file.h"

#include "log_level.h"
#include "hdf5output.h"

namespace dsf
{
    namespace sim
    {
        /**
         * @brief CSV/HDF5 telemetry output handler.
         */
        class Output : public Block
        {
        public:
            Output(double _rate)
            {
                out = NULL;
                h5 = NULL;
                rate = _rate;
                rptRate = _rate;
                
                // Use Global Defaults
                csv_enabled = defaultCSV();
                h5_enabled = defaultHDF5(); 
                csv_level = defaultCSVLevel();
                h5_level = defaultHDF5Level();

                if (h5_enabled) h5 = new HDF5Output();
                
                title.resize(3);
                units.resize(3);
                conversion.resize(3);
            }
            
            ~Output()
            {
                if (h5) delete h5;
            }
            
            // Global Default Getters/Setters
            static bool& defaultCSV();
            static bool& defaultHDF5();
            static LogLevel& defaultCSVLevel();
            static LogLevel& defaultHDF5Level();

            void setHDF5(bool enable) { 
                h5_enabled = enable;
                if (h5_enabled && !h5) h5 = new HDF5Output();
            }
            void setCSV(bool enable) { csv_enabled = enable; }
            void setLogLevel(LogLevel csv, LogLevel h5v) { csv_level = csv; h5_level = h5v; }

            /** @brief Write all registered values to file. */
            void report()
            {
                if (csv_enabled && out) {
                    *out << t();
                    for (unsigned int i=0; i < doubles.size(); i++)
                        *out << ", " << *doubles[i] * conversion[0][i];
                    for (unsigned int i=0; i < vectors.size(); i++)
                        *out << ", " << (*vectors[i]).x * conversion[1][i] << ", " << (*vectors[i]).y * conversion[1][i] << ", " << (*vectors[i]).z * conversion[1][i];
                    for (unsigned int i=0; i < matrices.size(); i++)
                        *out << ", " << *matrices[i] * conversion[2][i];
                    *out << endl;
                }
                
                if (h5_enabled && h5) {
                    h5->report(t());
                }
            };

            /** @brief Open output file and write headers. */
            void open()
            {
                // Determine Filename (Base)
                // If CSV enabled, use "output.csv" convention. If HDF5 only, same convention.
                string filename = "output.csv"; 
                // get_unique_file returns "outputN.csv" and "outputN". 
                // Actually dsf::util::get_unique_file returns struct with .filename ("outputN.csv")
                
                // We want base name "outputN".
                // I'll assume get_unique_file logic handles extension.
                // If I pass "output", it searches "output", "output1"...
                // If I pass "output.csv", it searches "output.csv", "output0.csv"...
                
                std::string unique_csv = dsf::util::get_unique_file(filename).filename;
                // Strip .csv
                std::string base = unique_csv.substr(0, unique_csv.find_last_of("."));
                
                if (csv_enabled) {
                    string f = base + ".csv";
                    out = new ofstream(f.c_str(), ios::out);
                    out->precision(10);
                    out->width(10);
                    writeHeader();
                }
                
                if (h5_enabled && h5) {
                     h5->open(base); // HDF5Output appends .h5
                }
            }

            void init()     { 
                // Initialize HDF5 object if enabled but not created?
                // Logic fix: h5 object must exist to receive add() calls.
                // So create it in constructor? No, don't want dependency if disabled.
                // Create it in setHDF5(true).
                
                if ( out == NULL) open(); 
                report(); 
            }
            void rpt()      { report(); };                          
            void finalize() { 
                if (out) { out->close(); }
                if (h5) { h5->finalize(); }
            };

            /// @name Registration Methods
            /// @{
            
            // Legacy Overloads (Default to NORMAL)
            void add(double &d, string title, string units, double conversion=1.0) {
                add(d, title, units, LOG_NORMAL, conversion);
            }
            void add(dsf::util::Vec3 &v, string title, string units, double conversion=1.0) {
                add(v, title, units, LOG_NORMAL, conversion);
            }
            void add(dsf::util::Mat3 &m, std::string title, std::string units, double conversion=1.0) {
                add(m, title, units, LOG_NORMAL, conversion);
            }

            // Priority Overloads
            void add(double &d, string t, string u, LogLevel p, double c=1.0)
            {
                if (p <= csv_level) {
                    doubles.push_back(&d);
                    this->title[0].push_back(t);
                    this->units[0].push_back(u);
                    this->conversion[0].push_back(c);
                }
                if (h5_enabled && h5 && p <= h5_level) {
                    h5->add(d, t, u, c);
                }
            }

            void add(dsf::util::Vec3 &v, string t, string u, LogLevel p, double c=1.0)
            {
                if (p <= csv_level) {
                    vectors.push_back(&v);
                    this->title[1].push_back(t);
                    this->units[1].push_back(u);
                    this->conversion[1].push_back(c);
                }
                if (h5_enabled && h5 && p <= h5_level) {
                    h5->add(v, t, u, c);
                }
            }

            void add(dsf::util::Mat3 &m, std::string t, std::string u, LogLevel p, double c=1.0)
            {
                if (p <= csv_level) {
                    matrices.push_back(&m);
                    this->title[2].push_back(t);
                    this->units[2].push_back(u);
                    this->conversion[2].push_back(c);
                }
                if (h5_enabled && h5 && p <= h5_level) {
                    h5->add(m, t, u, c);
                }
            }
            /// @}

        private:
            void writeHeader() {
                // Original header writing logic...
                *out <<" Time ";
                for (unsigned int i=0; i < title.size(); i++) {
                    for (unsigned int j=0; j < title[i].size(); j++) {
                        if ( i == 1) {
                            *out << ", " << title[i][j] << " (x) " << ", " << title[i][j] << " (y) " << ", " << title[i][j] << " (z) ";
                        }
                        else
                            *out << ", " <<  title[i][j];
                    }
                }
                *out << endl;
                *out << " [s] ";
                for (unsigned int i=0; i < units.size(); i++) {
                    for (unsigned int j=0; j < title[i].size(); j++) {
                         if ( i == 1) {
                            *out << ", " << units[i][j] << ", " <<  units[i][j] << ", " <<  units[i][j];
                        }
                        else
                            *out << ", " <<  units[i][j];
                    }
                }
                *out << endl;
            }

            double rate;                                
            vector< vector< std::string> >title;        
            vector< vector< std::string> >units;        
            vector< vector<      double> >conversion;   
            vector< double *>doubles;                   
            vector< dsf::util::Vec3 *>vectors;          
            vector< dsf::util::Mat3 *>matrices;         
            ofstream *out;     

            // HDF5 Support
            HDF5Output *h5;
            bool csv_enabled;
            bool h5_enabled;
            LogLevel csv_level;
            LogLevel h5_level;
        };
    }
}
