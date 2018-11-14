#pragma once

	// Updated for DSF
#include "util/math/vec3.h"
#include "util/tbl/tbl.h"
#include "sim/block.h"

class EarthBase;
class ScriptedTarget : public dsf::sim::Block
{
public:
	ScriptedTarget() {};
	static Block *block;

	void init(void);
	void update(void);
	void rpt(void);
	void finalize(void);
	void configure(dsf::xml::xmlnode n);

	// Accessors
	dsf::util::Vec3 Position(double t);

protected:
	EarthBase * rbeq;
	
	bool error;								// true = error corrution, false = no error corruption

	dsf::util::Vec3 xyz;					// true position
	dsf::util::Vec3 xyz_err;				// corrupted position

	double NMD, NMDold;						// NMD tracking
	double stdev, mean;						// gaussian variables
	double mortarTime;						// time offset for table interp

	dsf::util::Table MortarXTab;
	dsf::util::Table MortarYTab;
	dsf::util::Table MortarZTab;
};