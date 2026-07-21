#include "output.h"

namespace dsf {
namespace sim {

bool& Output::defaultCSV() { 
    static bool b = true; 
    return b; 
}

bool& Output::defaultHDF5() { 
    static bool b = false; 
    return b; 
}

LogLevel& Output::defaultCSVLevel() { 
    static LogLevel l = LOG_NORMAL; 
    return l; 
}

LogLevel& Output::defaultHDF5Level() {
    static LogLevel l = LOG_VERBOSE;
    return l;
}

// Defined here rather than in block.h because Output is an incomplete type
// there (output.h includes block.h). See the declaration for rationale.
void Block::applyOutputGroup() {
    // Per-vehicle grouping: channels registered by this block's init() land
    // under its parent element's name= ("F16_Altitude" in CSV, /F16/... in
    // HDF5). Empty vehicle_group (sim-level blocks) logs at the root. A block
    // may still call setGroupName() in its own init() to override.
    if (o) o->setGroupName(vehicle_group);
}

}
}
