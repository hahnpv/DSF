#pragma once

#include "util/math/vec3.h"
#include "util/math/mat3.h"

// the smallest subassembly of a stage
// everything is done in a body reference frame, but not the body frame from the rigid body eqns
// (that body frame is centered on the CM which is a moving target). This frame will need to be 
// defined. Most likely (0,0,0) will occur at the bottom center of the vehicle to allow for symmetry
// and then be positive X up, and y/z out the sides.

// this is just to hold pieces of data, no computation. 
struct Component
{
public:
	Component() {};
	static dsf::sim::Block *block;

	Component( dsf::util::Vec3 position, dsf::util::Mat3 MOI, double mass)
	{
		this->position = position;
		this->MOI = MOI;
		this->mass = mass;
	}
	void rotate(dsf::util::Mat3 m)			// Rotate by a rotation matrix, m
	{
		MOI = m * MOI * m.inv();
	}
	double mass;
	dsf::util::Vec3 position;
	dsf::util::Mat3 MOI;
};
