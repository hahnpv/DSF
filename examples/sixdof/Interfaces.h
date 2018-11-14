#pragma once

//
//	Interfaces to provide common access to information
//

#include "util/math/vec3.h"
#include "util/math/mat3.h"

class ForceAndMoment
{
public:
	virtual dsf::util::Vec3 force()  { return dsf::util::Vec3(0,0,0); };
	virtual dsf::util::Vec3 moment() { return dsf::util::Vec3(0,0,0); };
};

class MassInterface
{
public:
	virtual dsf::util::Mat3 MOI() {	return Mat3(1,0,0, 0,1,0, 0,0,1); };
	virtual double m()			  { return 1.; };
};
