#pragma once
#include "sim/block.h"
#include "util/math/vec3.h"

class Bouncy : public dsf::sim::Block 
{
public:
	Bouncy(void);
	static Block * block;

	void init(void);
	void update(void);
	void rpt(void);
	void finalize(void);

	void configure(dsf::xml::xmlnode n);

protected:
	dsf::util::Vec3 xyz;					///< position; Inertial
	dsf::util::Vec3 dxdydz;					///< position derivative
	dsf::util::Vec3 uvw;					///< velocity; Body
	dsf::util::Vec3 dudvdw;					///< velocity derivative
	dsf::util::Vec3 orient;					///< dummy orientation for Vis

	dsf::util::Vec3 g;				///< Gravity
	double m;						///< Mass
	double e;						///< Coefficient of Restoration
};