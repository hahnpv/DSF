#pragma once

#include "PropBase.h"
#include "util/tbl/tbl.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

class RocketProp : public PropBase
{
public:
	RocketProp() {};

	static Block *block;

	virtual void update();
	virtual void configure(dsf::xml::xmlnode n);
	
	virtual dsf::util::Vec3 moment()	{ return XYZ; };
	virtual dsf::util::Vec3 force()		{ return LMN; };

private:
	bool is_firing;								///< firing flag
	double Isp;									///< ISP of propellant
	double mdot;								///< mass flow rate
	double g_0;									///< gravity
	dsf::util::Vec3 s_b;						// distance from CM to propulsion; body coordinates
	dsf::util::Vec3 XYZ;
	dsf::util::Vec3 LMN;
};
