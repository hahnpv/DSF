#include <pybind11/pybind11.h>
#include "bindings.h"

PYBIND11_MODULE(dsf, m) {
    init_util(m);
    init_sim(m);
    init_net(m);
}
