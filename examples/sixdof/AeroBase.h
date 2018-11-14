#pragma once

#include "sim/block.h"
#include "util/tbl/tbl.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

#include "Interfaces.h"

class AeroBase : public dsf::sim::Block, public ForceAndMoment
{
public:
	AeroBase() {};

	static Block *block;

	virtual void configure(dsf::xml::xmlnode n) {};
	virtual void update(double M, double rho, dsf::util::Vec3 uvw_b, dsf::util::Vec3 pqr) {};
/*	virtual dsf::util::Vec3 moments()
	{
		return Vec3(0,0,0);
	}
	virtual dsf::util::Vec3 forces()
	{
		return Vec3(0,0,0);
	}*/
private:
};
