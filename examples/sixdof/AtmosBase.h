#pragma once

#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"

class AtmosBase : public dsf::sim::Block
{
public:
	AtmosBase(void) {};
	static Block *block;
	virtual void update(double alt, dsf::util::Vec3 uvw) {};
	virtual double rho()  { return 0.; };
	virtual double Mach() { return 0.; };
};
