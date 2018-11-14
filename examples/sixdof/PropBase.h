#pragma once

#include "sim/block.h"
#include "util/tbl/tbl.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

class PropBase : public dsf::sim::Block
{
public:
	PropBase() {};

	static Block *block;

	virtual void update() {};
	virtual void configure(dsf::xml::xmlnode n) {};

	virtual dsf::util::Vec3 moment()
	{
		return Vec3(0,0,0);
	}
	virtual dsf::util::Vec3 force()
	{
		return Vec3(0,0,0);
	}
private:
};
