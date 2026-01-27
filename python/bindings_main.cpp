#include <pybind11/embed.h>
#include "bindings.h"

PYBIND11_EMBEDDED_MODULE(dsf, m) {
    init_util(m);
    init_sim(m);
    init_net(m);
}
