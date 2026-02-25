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

            /** @brief Set the HDF5 group name (block/vehicle ID) for hierarchical output. */
            void setGroupName(const std::string& gname) { h5_group_name = gname; }

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
                // CSV: find a unique "outputN.csv" base
                string filename = "output.csv";
                std::string unique_csv = dsf::util::get_unique_file(filename).filename;
                std::string csv_base = unique_csv.substr(0, unique_csv.find_last_of("."));

                if (csv_enabled) {
                    string f = csv_base + ".csv";
                    out = new ofstream(f.c_str(), ios::out);
                    out->precision(10);
                    out->width(10);
                    writeHeader();
                }

                if (h5_enabled && h5) {
                     // Use explicitly-set group name (e.g. from setGroupName()) first.
                     // Fall back to parent-chain walk for blocks that live in the block tree.
                     std::string bname = h5_group_name;
                     if (bname.empty()) {
                         for (Block* b = getParent(); b != nullptr; b = b->getParent()) {
                             std::string n = b->getName();
                             if (!n.empty()) { bname = n; break; }
                         }
                     }
                     if (!bname.empty()) h5->setGroup(bname);

                     // Get a unique HDF5 filename independently (avoids re-using stale .h5 files)
                     std::string unique_h5 = dsf::util::get_unique_file("output.h5").filename;
                     std::string h5_base = unique_h5.substr(0, unique_h5.find_last_of("."));
                     h5->open(h5_base);
                }
            }

            void init()     {
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

            /// @name Real-Time Accessors
            /// @{
            std::vector<std::string> get_header_names() {
                std::vector<std::string> names;
                // Doubles
                for (const auto& t : title[0]) names.push_back(t);
                // Vectors (x, y, z)
                for (const auto& t : title[1]) {
                    names.push_back(t + " (x)");
                    names.push_back(t + " (y)");
                    names.push_back(t + " (z)");
                }
                // Matrices (9 elements)
                for (const auto& t : title[2]) {
                    names.push_back(t + " (0,0)"); names.push_back(t + " (0,1)"); names.push_back(t + " (0,2)");
                    names.push_back(t + " (1,0)"); names.push_back(t + " (1,1)"); names.push_back(t + " (1,2)");
                    names.push_back(t + " (2,0)"); names.push_back(t + " (2,1)"); names.push_back(t + " (2,2)");
                }
                return names;
            }

            std::vector<double> get_current_values() {
                std::vector<double> vals;
                // Pre-allocate to avoid reallocs
                vals.reserve(doubles.size() + vectors.size()*3 + matrices.size()*9);
                
                // Doubles
                for (size_t i = 0; i < doubles.size(); ++i) {
                    vals.push_back(*doubles[i] * conversion[0][i]);
                }
                // Vectors
                for (size_t i = 0; i < vectors.size(); ++i) {
                    double c = conversion[1][i];
                    vals.push_back(vectors[i]->x * c);
                    vals.push_back(vectors[i]->y * c);
                    vals.push_back(vectors[i]->z * c);
                }
                // Matrices
                for (size_t i = 0; i < matrices.size(); ++i) {
                    double c = conversion[2][i];
                    const auto& m = *matrices[i];
                    // Correct access via row vectors (a0, a1, a2)
                    vals.push_back(m.a0.x * c); vals.push_back(m.a0.y * c); vals.push_back(m.a0.z * c);
                    vals.push_back(m.a1.x * c); vals.push_back(m.a1.y * c); vals.push_back(m.a1.z * c);
                    vals.push_back(m.a2.x * c); vals.push_back(m.a2.y * c); vals.push_back(m.a2.z * c);
                }
                return vals;
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
            std::string h5_group_name; ///< Explicit group name for HDF5 hierarchy (set via setGroupName)
        };

    }
}
