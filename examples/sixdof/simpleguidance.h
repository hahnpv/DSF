#pragma once

#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/tbl/tbl.h"
#include "squib.h"

#include "Interfaces.h"

#include <map>
class Squib;
class Linear;
class ScriptedTarget;
class EarthBase;
	/// inherits off Block to get access to time, output, etc. May not be directly integrated... see what makes sense.
class SimpleGuidance : public dsf::sim::Block, public ForceAndMoment
{
public:
	SimpleGuidance();
	static Block * block;

	void init();
	void update();
	void rpt();
	void finalize();
	void configure(dsf::xml::xmlnode n);

	inline dsf::util::Vec3 moment() {
		dsf::util::Vec3 moments;
		for (int i=0; i<numSquibs; i++)
			if (SquibPack[i]->firing_bit())
				moments += SquibPack[i]->moment();
		return moments;
	};
	inline dsf::util::Vec3 force() {
		dsf::util::Vec3 forces;
		for (int i=0; i< numSquibs; i++)
			if (SquibPack[i]->firing_bit())
				forces += SquibPack[i]->forces();
		return forces;
	};

	void set_state (void) {			// set pause.
		state = t() + wait;
	}

	EarthBase * rbeq;
	ScriptedTarget   *target_model;
	
protected:
	bool stateError;		// error flag for state information
	bool phaseError;		// error flag for phase 
							// (will already be corrupted if state
							// is erroneous)

	double magnitude;				// distance
	double phase;					// angular clocking
	double state, state_0, wait;	// squib firing controls (when to start, minumum squib turnaround time)
	double time;					// projected intercept time  

	int numSquibs;
	double squib_integration_time;
	double squib_dt;
	double numSquibsFired;
	dsf::util::Vec3 xyz_body;
	dsf::util::Vec3 xyz_err;
	dsf::util::Vec3 target_output;

	double gaussPhaseBias;

	dsf::util::Vec3 staticTarget;	// TEMPORARY for static performance runs

	vector<dsf::util::Table*>pwt;

	std::map<dsf::util::Vec3, double> LinearizedModel;

	vector<Squib*>SquibPack;
	vector<Squib*>::iterator squib_iter;

	Linear	   *LinearModel;

};