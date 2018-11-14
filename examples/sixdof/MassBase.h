#pragma once

#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"
#include "Interfaces.h"

class MassBase : public dsf::sim::Block, public MassInterface
{
public:
	MassBase(void) {};
	static Block *block;

	virtual void update() {};

	virtual dsf::util::Mat3 MOI()
	{
		return Mat3(1,0,0, 0,1,0, 0,0,1);
	}
	virtual double m()
	{
		return 1.;
	}

	void configure(dsf::xml::xmlnode n) {};
};
