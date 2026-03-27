#include <pybind11/pybind11.h>
#include "bindings.h"

PYBIND11_MODULE(dsf_core, m) {
    m.doc() = "DSF Python Wrapper"; // optional module docstring

    // Expose core types/functions
    init_util(m);
    init_sim(m);
}
