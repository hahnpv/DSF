#include "EarthBase.h"
#include "sim/TRefDict.h"
#include "AeroBase.h"
#include "AtmosBase.h"
#include "MassBase.h"
dsf::sim::Block* EarthBase::block = dsf::sim::TClass<EarthBase,Block>::Instance()->getStatic();
