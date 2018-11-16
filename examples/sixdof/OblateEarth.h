#pragma once

#include "EarthBase.h"
#include "wgs84.h"
class OblateEarth : public EarthBase 
{
public:
	OblateEarth(void);
	static Block *block;

	void init(void);
	void update(void);
	void rpt(void);
	void finalize(void);

	void configure(dsf::xml::xmlnode n);

	dsf::util::Vec3 position()		{ return xyz_e; };
	dsf::util::Vec3 velocity()		{ return uvw_b; };
//	dsf::util::Mat3 _Teb()			{ return e->T_e_i((e->w_e_i[2] * t())) * Mat3(1,0,0,0,1,0,0,0,-1) * T_b_i.inv(); };
//	dsf::util::Mat3 _Teb()			{ return e->T_e_i((e->w_e_i[2] * t())) * Mat3(1,0,0,0,1,0,0,0,-1) * Mat3(0,0,1, 0,1,0, 1,0,0) * T_b_i.inv(); };
	dsf::util::Mat3 _Teb()			{ return Mat3(1,0,0,0,1,0,0,0,-1) * (Mat3(0,0,1, 0,1,0, 1,0,0) * e->T_e_i((e->w_e_i[2] * t()))); };	// quasi-NED

protected:

	WGS84 *e;						///< WGS84 Model Reference
	Position p;						///< WGS84 Position Struct

	dsf::util::Mat3 T_b_i;			///< Body WRT Inertial TM
	dsf::util::Mat3 dT_b_i;			///< Body WRT Inertial TM derivative tensor
	dsf::util::Mat3 I;				///< Identity matrix; T_b_i orthogonalization

	dsf::util::Vec3 xyz_d;			///< XYZ in geodetic coordinates
	dsf::util::Vec3 xyz_e;			///< XYZ in geodetic coordinates
	dsf::util::Vec3 uvw_b;			///< body frame = T_b_i * uvw + rotational dynamics
	dsf::util::Vec3 xyz_0;			///< initial position, inertial
};
