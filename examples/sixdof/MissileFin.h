#pragma once

#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"

#include "Interfaces.h"

struct Fin
{
	double Cl;					// simplified aero - Cl*alpha		
	double Cd0;					// simplified aero - Cd0 + Cl*alpha^2
	double delta;				// displacement
	double theta;				// rotation of [B
	dsf::util::Vec3 sbf;		// location relative to CM, body frame [later to fixed ref pt as cm may shift]
	dsf::util::Mat3 Tbf;		// transformation from fin->body
};

class EarthBase;
class MissileFin : public dsf::sim::Block, public ForceAndMoment
{
public:
	MissileFin(void) {};
	static Block *block;

	void update();
	void configure(dsf::xml::xmlnode n);

	dsf::util::Vec3 force()  { return XYZ; };
	dsf::util::Vec3 moment() { return LMN; };

private:
	EarthBase * earth;

	int nfin;
	std::vector< Fin> fin;
	dsf::util::Vec3 XYZ;
	dsf::util::Vec3 LMN;
};
