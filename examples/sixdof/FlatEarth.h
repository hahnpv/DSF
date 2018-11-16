#pragma once

#include "EarthBase.h"

class SimpleGuidance;
class FlatEarth : public EarthBase
{
public:
	FlatEarth(void);
	static Block * block;

	void update_matrices(void);

	void init(void);
	void update(void);
	void rpt(void);
	void finalize(void);

	void normalize(void);
	void configure(dsf::xml::xmlnode n);

	dsf::util::Mat3 _Teb()			{ return T_e_b; };

protected:
	double q0, q1, q2, q3;			///< Quaternion
	double dq0, dq1, dq2, dq3;		///< Quaternion Derivative

	dsf::util::Vec3 g;				///< Gravity in the Inertial frame
	dsf::util::Vec3 g_b;			///< Gravity in the Body frame

	dsf::util::Mat3 T_e_b;			///< Body WRT Inertial TM

};