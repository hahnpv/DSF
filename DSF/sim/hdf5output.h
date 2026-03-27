/**
 * @file hdf5output.h
 * @brief HDF5 output handler — self-describing telemetry files.
 *
 * Each dataset gets:
 *   - "units"             (string attribute, e.g. "m", "rad", "m/s")
 *   - "long_name"         (string attribute, full descriptive name)
 *   - "conversion_factor" (double attribute, only if != 1.0)
 *
 * File root attributes:
 *   - "dsf_version", "created", "xml_file", "xml_content", "dt", "tmax"
 */
#pragma once

#include <iostream>
#include <vector>
#include <string>
#include <set>
#include <map>
#include <ctime>
#include <iomanip>
#include <sstream>

#include "H5Cpp.h"
#include "log_level.h"
#include "../util/math/vec3.h"
#include "../util/math/mat3.h"
#include "../util/math/quat.h"
#include <unistd.h>  // for access()

namespace dsf
{
    namespace sim
    {
        /**
         * @brief HDF5 Logger — self-describing simulation output.
         *
         * Writes simulation variables to HDF5 datasets with full metadata.
         * Each variable gets its own dataset organised into named groups.
         */
        class HDF5Output
        {
        public:
            HDF5Output() : file(nullptr), frame_count(0), file_ready(false),
                           meta_dt(0.0), meta_tmax(0.0)
            {
            }

            ~HDF5Output()
            {
                finalize();
            }

            /** @brief Set the current group name for subsequent add() calls. */
            void setGroup(const std::string& name)
            {
                current_group = name;
            }

            /** @brief Set output base filename (derived from XML name). */
            void setBaseName(const std::string& name)
            {
                base_name = name;
            }

            /** @brief Store simulation metadata—written as root attributes on file creation. */
            void setMetadata(const std::string& xml_file,
                             const std::string& xml_content,
                             double dt, double tmax)
            {
                meta_xml_file    = xml_file;
                meta_xml_content = xml_content;
                meta_dt          = dt;
                meta_tmax        = tmax;
            }

            void finalize()
            {
                // Close all open groups
                for (auto& kv : groups) {
                    if (kv.second) { delete kv.second; kv.second = nullptr; }
                }
                groups.clear();
                if (file) { file->close(); delete file; file = nullptr; }
            }

            void open(std::string filename)
            {
                // Defer actual file creation to first report().
                // At open() time, not all blocks may have registered variables yet.
                if (filename.find(".h5") == std::string::npos) filename += ".h5";
                deferred_filename = filename;
                file_ready = false;
            }

            /// Actually create the HDF5 file (called on first report)
            void createFile()
            {
                if (file_ready || deferred_filename.empty()) return;
                try {
                file = new H5::H5File(deferred_filename, H5F_ACC_TRUNC);

                // ---- Write root-level metadata attributes ----
                writeRootMetadata();

                // Create groups for all unique group names
                for (const auto& gname : used_groups) {
                    if (!gname.empty() && groups.find(gname) == groups.end()) {
                        groups[gname] = new H5::Group(file->createGroup(gname));
                    }
                }

                // Create Time dataset at file root
                createDatasetAt("Time", H5::PredType::NATIVE_DOUBLE, nullptr, "s", "Time", 1.0);

                // Create datasets for all registered variables
                for (size_t i = 0; i < titles.size(); i++)
                    createDatasetAt(titles[i], H5::PredType::NATIVE_DOUBLE,
                                    groupFor(var_groups[i]),
                                    unit_strings[i], titles[i], conversions[i]);

                for (size_t i = 0; i < vec_titles.size(); i++) {
                    H5::Group* g = groupFor(vec_var_groups[i]);
                    createDatasetAt(vec_titles[i] + "_x", H5::PredType::NATIVE_DOUBLE, g,
                                    vec_units[i], vec_titles[i] + " (x)", vec_conversions[i]);
                    createDatasetAt(vec_titles[i] + "_y", H5::PredType::NATIVE_DOUBLE, g,
                                    vec_units[i], vec_titles[i] + " (y)", vec_conversions[i]);
                    createDatasetAt(vec_titles[i] + "_z", H5::PredType::NATIVE_DOUBLE, g,
                                    vec_units[i], vec_titles[i] + " (z)", vec_conversions[i]);
                }

                for (size_t i = 0; i < quat_titles.size(); i++) {
                    H5::Group* g = groupFor(quat_var_groups[i]);
                    createDatasetAt(quat_titles[i] + "_x", H5::PredType::NATIVE_DOUBLE, g,
                                    quat_units[i], quat_titles[i] + " (x)", quat_conversions[i]);
                    createDatasetAt(quat_titles[i] + "_y", H5::PredType::NATIVE_DOUBLE, g,
                                    quat_units[i], quat_titles[i] + " (y)", quat_conversions[i]);
                    createDatasetAt(quat_titles[i] + "_z", H5::PredType::NATIVE_DOUBLE, g,
                                    quat_units[i], quat_titles[i] + " (z)", quat_conversions[i]);
                    createDatasetAt(quat_titles[i] + "_w", H5::PredType::NATIVE_DOUBLE, g,
                                    quat_units[i], quat_titles[i] + " (w)", quat_conversions[i]);
                }

                for (size_t k = 0; k < mat_titles.size(); k++) {
                    H5::Group* g = groupFor(mat_var_groups[k]);
                    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++)
                        createDatasetAt(mat_titles[k] + "_" + std::to_string(i) + std::to_string(j),
                                      H5::PredType::NATIVE_DOUBLE, g,
                                      mat_units[k],
                                      mat_titles[k] + " (" + std::to_string(i) + "," + std::to_string(j) + ")",
                                      mat_conversions[k]);
                }

                file_ready = true;
                } catch (H5::Exception& e) {
                    std::cerr << "HDF5 Open Failed for: " << deferred_filename 
                              << " (" << e.getDetailMsg() << ")" << std::endl;
                    if (file) { delete file; file = nullptr; }
                } catch (...) {
                    std::cerr << "HDF5 Open Failed for: " << deferred_filename << std::endl;
                    if (file) { delete file; file = nullptr; }
                }
            }
            
            /// Registration: store pointers, titles, units, and group tags.
            void add(double &d, std::string title, std::string units, double conversion=1.0)
            {
                doubles.push_back(&d);
                titles.push_back(title);
                unit_strings.push_back(units);
                conversions.push_back(conversion);
                var_groups.push_back(current_group);
                used_groups.insert(current_group);
            }

            void add(dsf::util::Vec3 &v, std::string title, std::string units, double conversion=1.0)
            {
                vectors.push_back(&v);
                vec_titles.push_back(title);
                vec_units.push_back(units);
                vec_conversions.push_back(conversion);
                vec_var_groups.push_back(current_group);
                used_groups.insert(current_group);
            }

            void add(dsf::util::Quaternion &q, std::string title, std::string units, double conversion=1.0)
            {
                quats.push_back(&q);
                quat_titles.push_back(title);
                quat_units.push_back(units);
                quat_conversions.push_back(conversion);
                quat_var_groups.push_back(current_group);
                used_groups.insert(current_group);
            }
            
            void add(dsf::util::Mat3 &m, std::string title, std::string units, double conversion=1.0)
            {
                matrices.push_back(&m);
                mat_titles.push_back(title);
                mat_units.push_back(units);
                mat_conversions.push_back(conversion);
                mat_var_groups.push_back(current_group);
                used_groups.insert(current_group);
            }

            void report(double t)
            {
                // Lazy file creation on first report
                if (!file_ready) createFile();
                if (!file) return;
                
                // Write Time (always at root)
                appendAt("Time", t, nullptr);

                // Write Doubles
                for (size_t i=0; i < doubles.size(); i++) {
                    appendAt(titles[i], *doubles[i] * conversions[i], groupFor(var_groups[i]));
                }
                
                // Write Vectors
                for (size_t i=0; i < vectors.size(); i++) {
                    H5::Group* g = groupFor(vec_var_groups[i]);
                    appendAt(vec_titles[i] + "_x", vectors[i]->x * vec_conversions[i], g);
                    appendAt(vec_titles[i] + "_y", vectors[i]->y * vec_conversions[i], g);
                    appendAt(vec_titles[i] + "_z", vectors[i]->z * vec_conversions[i], g);
                }

                // Write Quaternions
                for (size_t i=0; i < quats.size(); i++) {
                    H5::Group* g = groupFor(quat_var_groups[i]);
                    appendAt(quat_titles[i] + "_x", quats[i]->q1 * quat_conversions[i], g);
                    appendAt(quat_titles[i] + "_y", quats[i]->q2 * quat_conversions[i], g);
                    appendAt(quat_titles[i] + "_z", quats[i]->q3 * quat_conversions[i], g);
                    appendAt(quat_titles[i] + "_w", quats[i]->q0 * quat_conversions[i], g);
                }
                
                // Write Matrices
                for (size_t k=0; k < matrices.size(); k++) {
                    dsf::util::Mat3& m = *matrices[k];
                    double c = mat_conversions[k];
                    H5::Group* g = groupFor(mat_var_groups[k]);
                    for(int i=0; i<3; i++) for(int j=0; j<3; j++) {
                         appendAt(mat_titles[k] + "_" + std::to_string(i) + std::to_string(j), m[i][j] * c, g);
                    }
                }
                
                frame_count++;
            }

        private:
            H5::H5File* file;
            std::map<std::string, H5::Group*> groups;  ///< Named groups (one per vehicle/block)
            std::string current_group;                   ///< Group name for current add() calls
            long frame_count = 0;
            std::string deferred_filename;
            std::string base_name;
            bool file_ready;

            // Simulation metadata
            std::string meta_xml_file;
            std::string meta_xml_content;
            double meta_dt;
            double meta_tmax;

            std::set<std::string> used_groups;          ///< All group names seen during registration
            
            // Per-variable data
            std::vector<double*> doubles;
            std::vector<std::string> titles;
            std::vector<std::string> unit_strings;
            std::vector<double> conversions;
            std::vector<std::string> var_groups;        ///< Group name for each double
            
            std::vector<dsf::util::Vec3*> vectors;
            std::vector<std::string> vec_titles;
            std::vector<std::string> vec_units;
            std::vector<double> vec_conversions;
            std::vector<std::string> vec_var_groups;    ///< Group name for each Vec3
            
            std::vector<dsf::util::Quaternion*> quats;
            std::vector<std::string> quat_titles;
            std::vector<std::string> quat_units;
            std::vector<double> quat_conversions;
            std::vector<std::string> quat_var_groups;
            
            std::vector<dsf::util::Mat3*> matrices;
            std::vector<std::string> mat_titles;
            std::vector<std::string> mat_units;
            std::vector<double> mat_conversions;
            std::vector<std::string> mat_var_groups;

            /// Write a string attribute on any H5Object (DataSet, Group, H5File)
            template<typename T>
            void writeStringAttr(T& loc, const std::string& name, const std::string& value)
            {
                H5::StrType strtype(H5::PredType::C_S1, H5T_VARIABLE);
                H5::DataSpace attr_space(H5S_SCALAR);
                H5::Attribute attr = loc.createAttribute(name, strtype, attr_space);
                attr.write(strtype, value);
            }

            /// Write a double attribute on any H5Object (DataSet, Group, H5File)
            template<typename T>
            void writeDoubleAttr(T& loc, const std::string& name, double value)
            {
                H5::DataSpace attr_space(H5S_SCALAR);
                H5::Attribute attr = loc.createAttribute(name, H5::PredType::NATIVE_DOUBLE, attr_space);
                attr.write(H5::PredType::NATIVE_DOUBLE, &value);
            }

            /// Write root-level metadata attributes
            void writeRootMetadata()
            {
                if (!file) return;

                // Timestamp
                std::time_t now = std::time(nullptr);
                std::tm* gmt = std::gmtime(&now);
                std::ostringstream ts;
                ts << std::put_time(gmt, "%Y-%m-%dT%H:%M:%SZ");
                writeStringAttr(*file, "created", ts.str());

                // DSF version (compile-time if available, else "unknown")
                #ifdef DSF_VERSION
                writeStringAttr(*file, "dsf_version", DSF_VERSION);
                #else
                writeStringAttr(*file, "dsf_version", "dev");
                #endif

                // XML config
                if (!meta_xml_file.empty())
                    writeStringAttr(*file, "xml_file", meta_xml_file);
                if (!meta_xml_content.empty())
                    writeStringAttr(*file, "xml_content", meta_xml_content);

                // Simulation parameters
                if (meta_dt > 0.0)
                    writeDoubleAttr(*file, "dt", meta_dt);
                if (meta_tmax > 0.0)
                    writeDoubleAttr(*file, "tmax", meta_tmax);
            }

            /// Get group pointer for a group name (nullptr = file root)
            H5::Group* groupFor(const std::string& gname) {
                if (gname.empty()) return nullptr;
                auto it = groups.find(gname);
                if (it != groups.end()) return it->second;
                return nullptr;
            }

            /// Create a dataset in a specific location with metadata attributes
            void createDatasetAt(const std::string& name, const H5::DataType& type,
                                 H5::Group* grp,
                                 const std::string& units = "",
                                 const std::string& long_name = "",
                                 double conversion = 1.0)
            {
                hsize_t dims[1]    = {0};
                hsize_t maxdims[1] = {H5S_UNLIMITED};
                H5::DataSpace dataspace(1, dims, maxdims);
                H5::DSetCreatPropList prop;
                hsize_t chunk_dims[1] = {1000};
                prop.setChunk(1, chunk_dims);
                prop.setDeflate(4);  // GZIP compression level 4

                try {
                    H5::DataSet ds;
                    if (grp) ds = grp->createDataSet(name, type, dataspace, prop);
                    else     ds = file->createDataSet(name, type, dataspace, prop);

                    // Write metadata attributes
                    if (!units.empty())
                        writeStringAttr(ds, "units", units);
                    if (!long_name.empty())
                        writeStringAttr(ds, "long_name", long_name);
                    if (conversion != 1.0)
                        writeDoubleAttr(ds, "conversion_factor", conversion);
                } catch (...) {}
            }

            /// Append a value to a dataset in a specific location
            void appendAt(const std::string& name, double value, H5::Group* grp)
            {
                try {
                    H5::DataSet ds;
                    if (grp) ds = grp->openDataSet(name);
                    else     ds = file->openDataSet(name);

                    hsize_t size[1]   = {(hsize_t)frame_count + 1};
                    ds.extend(size);

                    H5::DataSpace filespace = ds.getSpace();
                    hsize_t offset[1] = {(hsize_t)frame_count};
                    hsize_t dim1[1]   = {1};
                    filespace.selectHyperslab(H5S_SELECT_SET, dim1, offset);

                    hsize_t memdims[1] = {1};
                    H5::DataSpace memspace(1, memdims);
                    ds.write(&value, H5::PredType::NATIVE_DOUBLE, memspace, filespace);
                } catch (...) {}
            }
        };
    }
}
