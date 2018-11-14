#pragma once

#include "sim/block.h"

class AeroBase;
class AtmosBase;
class MassBase;
class SimpleGuidance;
class EarthBase : public dsf::sim::Block 
{
public:
	EarthBase(void) {};
	static Block *block;

	virtual void init(void) {};
	virtual void update(void) {};
	virtual void rpt(void) {};
	virtual void finalize(void) {};

	void configure(dsf::xml::xmlnode n) {};

	virtual dsf::util::Vec3 position()		{ return xyz; };
	virtual dsf::util::Vec3 velocity()		{ return uvw; };
	dsf::util::Vec3 rotvelocity()	
	{ 
		if(rollingAirframe)
			return Vec3(omega, pqr.y, pqr.z);
		else
			return pqr; 
	};
	virtual dsf::util::Vec3 Orientation()	{ return euler; };
	virtual dsf::util::Mat3 _Teb()			{ return dsf::util::Mat3(0,0,0, 0,0,0, 0,0,0); };

protected:
	bool rollingAirframe;					///< Rolling Airframe Selection
	double omega, domega;					///< Rolling Airframe roll rate

	// State and Derivative Vectors
	dsf::util::Vec3 xyz;					///< position; Inertial
	dsf::util::Vec3 dxdydz;					///< position derivative
	dsf::util::Vec3 uvw;					///< velocity; Body
	dsf::util::Vec3 dudvdw;					///< velocity derivative
	dsf::util::Vec3 pqr;					///< rotation; Body
	dsf::util::Vec3 pqr_b;					///< rotation; Body [spinning airframe]
	dsf::util::Vec3 dpdqdr;					///< rotation derivative
	dsf::util::Vec3 euler;					///< Euler Angles

	AtmosBase * atmos;						///< Atmosphere Base Model Reference
	AeroBase  *  aero;						///< Aerodynamic Base Model Reference
//	MassBase  *  mass;						///< Mass Base Model Reference
//	SimpleGuidance * gnc;					///< Guidance Model
};
