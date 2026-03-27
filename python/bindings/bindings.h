#pragma once
#include <pybind11/pybind11.h>

namespace py = pybind11;

void init_util(py::module_ &m);
void init_sim(py::module_ &m);
