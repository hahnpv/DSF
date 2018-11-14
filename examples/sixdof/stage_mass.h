#pragma once

#include "sim/block.h"

#include "util/math/vec3.h"
#include "util/math/mat3.h"

#include "component.h"

#include <vector>
	// a vehicle is composed of stages
	// a stage is composed of components
	// a component is simply a mass centered at a position, with a MOI tensor associated with it
	// all components are summed about the stage CM to get the stage CM/MOI/mass
	// all stages are summed to get the vehicle CM/MOI/mass

	// when staging occurs an external class (gnc) will take the appropriate stage from the
	// vehicle vector of vectors, delete it from this mass vector of vectors
	// and create a new vehicle class with its own rbeq, etc. Consideration will need to be 
	// made for a shift in cm, angular momentum applied, etc.

	// gnc is a friend class to remove stage vectors to create new stages at will
	// gnc may also be allowed to adjust mass properties on components representative
	// of fuel tanks while motors are firing.


	
	/*
		so far:
			- verified translation along x axis (2 - 1m height, 1m radius 1lb hollow cylinders stacked,
				centered at (1,0,0) have the same properties as 1 2m height, 1m radius, 2lb hollow 
				cylinder centered at (1,0,0).
	
			- verified a MOI tensor (Mat3) can be rotated by Mat3 rot * MOI * rot.inv()
				+ verified using the above 2 cylinder case: rotated about the x axis. No change in MOI terms
					as the body is symmetrical about the x axis (barring a slight error (e-17) in 
					cos/sin terms). 
				+ verified using the above 2 cylinder case: did rotation about z axis and the off axis terms
					changed. Set the angle to 90 degrees and the primary axis became the y axis, no off axis
					terms, and the secondary axes were x and z. Will add rotation method to component
	*/
class stageMass : public dsf::sim::Block
{
public:
	friend class gnc;

	static Block *block;

	stageMass(void);

	void update()
	{
		// during the update call, refresh the values of cm, mass, MOI
		// only when it is safe to sample (not in the integrator)

		if(1/*sample()*/)
		{
			// calculate total mass
			_m = 0;
			for (unsigned int i=0; i < vehicle.size(); i++)
			{
				for (unsigned int j=0; j < vehicle[i].size(); j++)
				{
					_m += vehicle[i][j].mass;
				}
			}

			// calculate center of mass
			// cm = 1/m * sum[i] ( m_i * x_i) 
			_cm = dsf::util::Vec3(0,0,0);
			for (unsigned int i=0; i < vehicle.size(); i++)
			{
				for (unsigned int j=0; j < vehicle[i].size(); j++)
				{	
					_cm += vehicle[i][j].position * vehicle[i][j].mass;
				}
			}
			_cm *= (1.0 / _m);

			// calculate MOI 
			// I_body = sum ( I ) about the cm
			// I_r_b = I_b_b + m_b * S_b_r.inv() * S_b_r
			// r = cm, b = object location
			_MOI = dsf::util::Mat3(0,0,0, 0,0,0, 0,0,0);
			for (unsigned int i=0; i < vehicle.size(); i++)
			{
				for (unsigned int j=0; j < vehicle[i].size(); j++)
				{	
					dsf::util::Vec3 Sbr = vehicle[i][j].position - _cm;
					_MOI += vehicle[i][j].MOI + Sbr.skew().transpose() * Sbr.skew() * vehicle[i][j].mass;
				}
			}
		}
	};

	void add_stage( std::vector< Component>stage)
	{
		vehicle.push_back( stage);
	}

	// create a new stage 
	// by splitting off an existing stage. Delete from this model.
	stageMass &split_stage( int stage)
	{
		stageMass *stage_two = new stageMass;
		stage_two->add_stage( this->vehicle[stage]);
		this->vehicle.erase(this->vehicle.begin()+stage);		// inefficient, I am told

		return *stage_two;
	}
	double mass()
	{
		return _m;
	};
	dsf::util::Vec3 cm()
	{
		return _cm;
	};
	dsf::util::Mat3 MOI()
	{
		return _MOI;
	};
private:
	std::vector< std::vector< Component>>vehicle;		// vehicle[stage_i][component_j]
	double _m;
	dsf::util::Vec3 _cm;
	dsf::util::Mat3 _MOI;
};
