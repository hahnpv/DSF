/**
 * @file hdf5output.h
 * @brief HDF5 output handler.
 */
#pragma once

#include <iostream>
#include <vector>
#include <string>

#include "H5Cpp.h"
#include "log_level.h"
#include "../util/math/vec3.h"
#include "../util/math/mat3.h"
#include <unistd.h>  // for access()

namespace dsf
{
    namespace sim
    {
        /**
         * @brief HDF5 Logger.
         * Writes simulation variables to HDF5 datasets.
         * Each variable gets its own dataset (Time Series).
         */
        class HDF5Output
        {
        public:
            HDF5Output() : file(nullptr), group(nullptr), frame_count(0)
            {
            }

            ~HDF5Output()
            {
                finalize();
            }

            /** @brief Set the HDF5 group name (block ID). Must be called before open(). */
            void setGroup(const std::string& name)
            {
                group_name = name;
            }

            void finalize()
            {
                if (group) { delete group; group = nullptr; }
                if (file)  { file->close(); delete file; file = nullptr; }
            }

            void open(std::string filename)
            {
                try {
                if (filename.find(".h5") == std::string::npos) filename += ".h5";

                // Always create fresh — each Output block has its own unique filename
                file = new H5::H5File(filename, H5F_ACC_TRUNC);

                // Write into a named group (set via setGroup before open)
                if (!group_name.empty())
                    group = new H5::Group(file->createGroup(group_name));

                // Pre-create datasets for variables registered before open()
                for (size_t i = 0; i < titles.size(); i++)
                    createDataset(titles[i], H5::PredType::NATIVE_DOUBLE);

                for (size_t i = 0; i < vec_titles.size(); i++) {
                    createDataset(vec_titles[i] + "_x", H5::PredType::NATIVE_DOUBLE);
                    createDataset(vec_titles[i] + "_y", H5::PredType::NATIVE_DOUBLE);
                    createDataset(vec_titles[i] + "_z", H5::PredType::NATIVE_DOUBLE);
                }

                for (size_t k = 0; k < mat_titles.size(); k++)
                    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++)
                        createDataset(mat_titles[k] + "_" + std::to_string(i) + std::to_string(j),
                                      H5::PredType::NATIVE_DOUBLE);

                } catch (...) {
                    std::cerr << "HDF5 Open Failed for: " << filename << std::endl;
                    if (file) { delete file; file = nullptr; }
                }
            }
            
            /// Registration Methods
            void add(double &d, std::string title, std::string units, double conversion=1.0)
            {
                doubles.push_back(&d);
                titles.push_back(title);
                // units unused in dataset layout effectively unless attributes
                conversions.push_back(conversion);
                
                // Create Dataset
                createDataset(title, H5::PredType::NATIVE_DOUBLE, units);
            }

            void add(dsf::util::Vec3 &v, std::string title, std::string units, double conversion=1.0)
            {
                vectors.push_back(&v);
                vec_titles.push_back(title);
                vec_conversions.push_back(conversion);
                
                createDataset(title + "_x", H5::PredType::NATIVE_DOUBLE, units);
                createDataset(title + "_y", H5::PredType::NATIVE_DOUBLE, units);
                createDataset(title + "_z", H5::PredType::NATIVE_DOUBLE, units);
            }
            
            // Matrices omitted for brevity unless needed (can add later)
            // Mat3 support:
             void add(dsf::util::Mat3 &m, std::string title, std::string units, double conversion=1.0)
            {
                matrices.push_back(&m);
                mat_titles.push_back(title);
                mat_conversions.push_back(conversion);
                // Mat3 is 9 doubles.
                // Could be 9 datasets or 1 dataset of array[9].
                // For simplicity: 9 datasets.
                for(int i=0; i<3; i++) for(int j=0; j<3; j++) {
                     createDataset(title + "_" + std::to_string(i) + std::to_string(j), H5::PredType::NATIVE_DOUBLE, units);
                }
            }

            void report(double t)
            {
                if (!file) return;
                
                // Write Time
                if (frame_count == 0) createDataset("Time", H5::PredType::NATIVE_DOUBLE);
                appendToDataset("Time", t);

                // Write Doubles
                for (size_t i=0; i < doubles.size(); i++) {
                    appendToDataset(titles[i], *doubles[i] * conversions[i]);
                }
                
                // Write Vectors
                for (size_t i=0; i < vectors.size(); i++) {
                    appendToDataset(vec_titles[i] + "_x", vectors[i]->x * vec_conversions[i]);
                    appendToDataset(vec_titles[i] + "_y", vectors[i]->y * vec_conversions[i]);
                    appendToDataset(vec_titles[i] + "_z", vectors[i]->z * vec_conversions[i]);
                }
                
                 // Write Matrices
                for (size_t k=0; k < matrices.size(); k++) {
                    dsf::util::Mat3& m = *matrices[k];
                    double c = mat_conversions[k];
                    for(int i=0; i<3; i++) for(int j=0; j<3; j++) {
                         appendToDataset(mat_titles[k] + "_" + std::to_string(i) + std::to_string(j), m[i][j] * c);
                    }
                }
                
                frame_count++;
            }

        private:
            H5::H5File* file;
            H5::Group*  group;       ///< Non-null when writing into a named group
            std::string group_name;  ///< Block ID used as group name
            long frame_count = 0;

            // Helper: create a dataset in the right location (file root or group)
            void createDatasetIn(const std::string& name, const H5::DataType& type, const std::string& units)
            {
                hsize_t dims[1]    = {0};
                hsize_t maxdims[1] = {H5S_UNLIMITED};
                H5::DataSpace dataspace(1, dims, maxdims);
                H5::DSetCreatPropList prop;
                hsize_t chunk_dims[1] = {1000};
                prop.setChunk(1, chunk_dims);

                H5::DataSet ds;
                if (group) ds = group->createDataSet(name, type, dataspace, prop);
                else       ds = file->createDataSet(name, type, dataspace, prop);

                if (!units.empty()) {
                    H5::StrType stype(H5::PredType::C_S1, units.length() + 1);
                    H5::DataSpace attr_space(H5S_SCALAR);
                    H5::Attribute attr = ds.createAttribute("units", stype, attr_space);
                    attr.write(stype, units.c_str());
                }
            }

            // Helper: open a dataset and append one double
            void appendIn(const std::string& name, double value)
            {
                H5::DataSet ds;
                if (group) ds = group->openDataSet(name);
                else       ds = file->openDataSet(name);

                hsize_t size[1]   = {(hsize_t)frame_count + 1};
                ds.extend(size);

                H5::DataSpace filespace = ds.getSpace();
                hsize_t offset[1] = {(hsize_t)frame_count};
                hsize_t dim1[1]   = {1};
                filespace.selectHyperslab(H5S_SELECT_SET, dim1, offset);

                hsize_t memdims[1] = {1};
                H5::DataSpace memspace(1, memdims);
                ds.write(&value, H5::PredType::NATIVE_DOUBLE, memspace, filespace);
            }
            
            std::vector<double*> doubles;
            std::vector<std::string> titles;
            std::vector<double> conversions;
            
            std::vector<dsf::util::Vec3*> vectors;
            std::vector<std::string> vec_titles;
            std::vector<double> vec_conversions;
            
            std::vector<dsf::util::Mat3*> matrices;
            std::vector<std::string> mat_titles;
            std::vector<double> mat_conversions;

            bool nameExists(const std::string& name)
            {
                if (group) return group->nameExists(name);
                if (file)  return file->nameExists(name);
                return false;
            }

            void createDataset(std::string name, const H5::DataType& type, std::string units = "")
            {
                if (!file) return;
                if (nameExists(name)) return;  // idempotent — skip if already created
                try { createDatasetIn(name, type, units); } catch (...) {}
            }

            void appendToDataset(std::string name, double value)
            {
                if (!file) return;
                try { appendIn(name, value); } catch (...) {}
            }
        };
    }
}
