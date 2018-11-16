#include "PropBase.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* PropBase::block = TClass<PropBase,Block>::Instance()->getStatic();
