#pragma once

// this should really be run parallel to airframe / wgs not sub to it
// re-work once wgs84 is generic
#include "AtmosBase.h"
#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"

class Atmosphere : public AtmosBase
{
public:
	Atmosphere(void);

	static Block *block;

//	void init(void);
	void update() {};									// default update for sim loop, for now
	void update(double alt, dsf::util::Vec3 uvw_b);		// update called by airframe model, for now
//	void rpt(void);
//	void finalize(void);

	double rho()
	{
		return Rho;
	}
	double Mach()
	{
		return M;
	}
	// TEMPORARY TEST
	double M;
	double Rho;
private:
	double Temp;
	double press;
};
