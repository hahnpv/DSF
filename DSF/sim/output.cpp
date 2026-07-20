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
void Block::resetOutputGroup() {
    if (o) o->setGroupName("");
}

}
}
