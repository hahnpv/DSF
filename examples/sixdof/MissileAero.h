#pragma once

#include "AeroBase.h"

#include "sim/block.h"

#include "util/tbl/tbl.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"

#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

class MissileAero : public AeroBase
{
public:
	MissileAero() {};		// req'd for class dictionary

	static Block *block;

	void configure(dsf::xml::xmlnode n);
	std::string filename;					/// table input filename
	double D;								/// reference diameter

	void update(double M, double rho, dsf::util::Vec3 uvw_b, dsf::util::Vec3 pqr);

	dsf::util::Vec3 moment()
	{
		return LMN;
	}
	dsf::util::Vec3 force()
	{
		return XYZ;
	}
private:

	// Aero tables
	dsf::util::Table Cx0;
	dsf::util::Table Cx2;
	dsf::util::Table Cy0;
	dsf::util::Table Cz0;
	dsf::util::Table CnA; 
	dsf::util::Table CypA;
	dsf::util::Table Clp;  
	dsf::util::Table Cmq; 
	dsf::util::Table CnpA;
	dsf::util::Table Cma;

	// Output
	dsf::util::Vec3 XYZ;
	dsf::util::Vec3 LMN;
};
