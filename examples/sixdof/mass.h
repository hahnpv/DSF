#pragma once
#include "MassBase.h"
#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

class Mass : public MassBase
{
public:
	Mass(void);
	static Block *block;

	void update();

	virtual dsf::util::Mat3 MOI()
	{
		return I;
	}
	virtual double m()
	{
		return M;
	}

	void configure(dsf::xml::xmlnode n);

private:
	double M;
	double area;
	dsf::util::Mat3 I;
};
