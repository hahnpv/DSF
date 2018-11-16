#pragma once

#include "util/math/vec3.h"
#include "util/tbl/tbl.h"
#include "sim/block.h"

class Squib : public dsf::sim::Block
{
public:
	Squib(double pulse_force_angle, double sl, int squib_number, bool dudcheck, bool thrustcoeff);

	void init(void);
	void update(double t, bool safe_sample);

	// Accessors
	dsf::util::Vec3 forces(void) { return XYZ; };
	dsf::util::Vec3 moment(void) { return LMN; };

	double get_pulse_force_angle(void) 	  { return pulse_force_angle; };
	void   set_squib()	{ firing = true; };									// set when squib is selected to be fired
	bool   firing_bit()	{ return firing; };									// check, if true integrate squib forces
	bool   status()		{ return squib_stat;   };							// checked to see if squib has been fired yet
	int    squib_num()	{ return squib_number; };
	double get_sl()		{ return sl; };
	void set_pulse_force_angle( double angle ) { pulse_force_angle = angle; };

protected:
	double pulse_force_angle;				// angular position of the squib on the projectile, rad
	double pulse_time_table_delay;			// time delay before squib can be fired, seconds DEPRECIATEd
	double phase, magnitude;				// accessors to the values output by the guidance module
	double firing_time;						// time firing was initiated
	double squib_integration_time;			// time counter during fine integration
	double thrust;							// thrust value read from table in text file.
	int squib_number;						// squib number designator
	int squib_state;						// 0 = not fired, 1 = firing

	double sl;								// station line position of the squib (offset along x axis)
	bool dud;								// dud squib flag.
	double c_star;							// thrust coefficient

	bool dudcheck, thrustcoeff;				// flags for checking for duds/thrust coefficient

	bool firing;							// firing bit = true while firing
	bool squib_stat;						// squib status: true till firing

	dsf::util::Vec3 XYZ;					// force vector
	dsf::util::Vec3 LMN;					// moment vector

	dsf::util::Table *ThrustProfile;
};