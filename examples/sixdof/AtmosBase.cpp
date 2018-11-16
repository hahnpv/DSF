#include "AtmosBase.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* AtmosBase::block = TClass<AtmosBase,Block>::Instance()->getStatic();
