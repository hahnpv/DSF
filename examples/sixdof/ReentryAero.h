#pragma once

#include "AeroBase.h"
#include "util/tbl/tbl.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

class ReentryAero : public AeroBase
{
public:
	ReentryAero() {};

	static Block *block;

	void configure(dsf::xml::xmlnode n);
	void update(double M, double rho, dsf::util::Vec3 uvw_b, dsf::util::Vec3 pqr);

	dsf::util::Vec3 moments()
	{
		return Vec3(0,0,0);
	}
	dsf::util::Vec3 forces()
	{
		return XYZ;
	}
private:
	dsf::util::Vec3 XYZ;
	double CdS;
};
