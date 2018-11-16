#include "AeroBase.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* AeroBase::block = TClass<AeroBase,Block>::Instance()->getStatic();
