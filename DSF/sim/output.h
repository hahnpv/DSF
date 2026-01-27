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

namespace dsf
{
    namespace sim
    {
        /**
         * @brief CSV telemetry output handler.
         * 
         * Blocks register state variables with Output, which writes them
         * to a timestamped CSV file at each report interval.
         * 
         * ## Usage
         * @code{.cpp}
         * // In block's configure or init:
         * o->add(position, "Position", "[m]");
         * o->add(velocity, "Velocity", "[m/s]");
         * @endcode
         */
        class Output : public Block
        {
        public:
            /**
             * @brief Construct output handler.
             * @param _rate Output sample rate [s].
             */
            Output(double _rate)
            {
                out = NULL;
                rate = _rate;
                rptRate = _rate;
                title.resize(2);
                units.resize(2);
                conversion.resize(2);
            }

            /** @brief Write all registered values to file. */
            void report()
            {
                *out << t();
                for (unsigned int i=0; i < doubles.size(); i++)
                {
                    *out << ", " << *doubles[i] * conversion[0][i];
                }
                for (unsigned int i=0; i < vectors.size(); i++)
                {
                    *out << ", " << (*vectors[i]).x * conversion[1][i] << ", " << (*vectors[i]).y * conversion[1][i] << ", " << (*vectors[i]).z * conversion[1][i];
                }
                for (unsigned int i=0; i < matrices.size(); i++)
                {
                    *out << ", " << *matrices[i] * conversion[2][i];
                }
                *out << endl;
            };

            /** @brief Open output file and write headers. */
            void open()
            {
                string filename = "output.csv";
                std::string file = dsf::util::get_unique_file(filename).filename;
                out = new ofstream(file.c_str(), ios::out);
                out->precision(10);
                out->width(10);
                *out <<" Time ";
                for (unsigned int i=0; i < title.size(); i++)
                {
                    for (unsigned int j=0; j < title[i].size(); j++)
                    {
                        if ( i == 1)
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
                        if ( i == 1)
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

            void init()     { if ( out == NULL) open(); report(); } ///< Open file and write initial state.
            void rpt()      { report(); };                          ///< Write current state to file.
            void finalize() { out->close(); };                      ///< Close output file.

            /// @name Registration Methods
            /// @{
            
            /**
             * @brief Register a scalar for output.
             * @param d          Reference to scalar variable.
             * @param title      Column title.
             * @param units      Unit string (e.g., "[m]").
             * @param conversion Optional scale factor (default 1.0).
             */
            void add(double &d, string title, string units, double conversion=1.0)
            {
                doubles.push_back(&d);
                this->title[0].push_back(title);
                this->units[0].push_back(units);
                this->conversion[0].push_back(conversion);
            }

            /**
             * @brief Register a Vec3 for output.
             * @param v          Reference to Vec3 variable.
             * @param title      Column title (x,y,z suffixes added automatically).
             * @param units      Unit string.
             * @param conversion Optional scale factor.
             */
            void add(dsf::util::Vec3 &v, string title, string units, double conversion=1.0)
            {
                vectors.push_back(&v);
                this->title[1].push_back(title);
                this->units[1].push_back(units);
                this->conversion[1].push_back(conversion);
            }

            /**
             * @brief Register a Mat3 for output.
             * @param m          Reference to Mat3 variable.
             * @param title      Column title.
             * @param units      Unit string.
             * @param conversion Optional scale factor.
             */
            void add(dsf::util::Mat3 &m, std::string title, std::string units, double conversion=1.0)
            {
                matrices.push_back(&m);
                this->title[2].push_back(title);
                this->units[2].push_back(units);
                this->conversion[2].push_back(conversion);
            }
            /// @}

        private:
            double rate;                                ///< Output sample rate [s].
            vector< vector< std::string> >title;        ///< Column titles by type.
            vector< vector< std::string> >units;        ///< Column units by type.
            vector< vector<      double> >conversion;   ///< Scale factors by type.
            vector< double *>doubles;                   ///< Registered scalar pointers.
            vector< dsf::util::Vec3 *>vectors;          ///< Registered Vec3 pointers.
            vector< dsf::util::Mat3 *>matrices;         ///< Registered Mat3 pointers.
            ofstream *out;                              ///< Output file stream.
        };
    }
}
