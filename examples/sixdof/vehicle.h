#pragma once

#include "sim/block.h"
#include "Interfaces.h"

	template <class TClass, class RType> 
	RType aggregate(std::vector<TClass*> &objvec, RType(TClass::*fpt)(void))
	{
		RType retval;
		for (unsigned int i=0; i < objvec.size(); i++)
		{
			retval += (*objvec[i].*fpt)();
		}
		return retval;
	}

class Vehicle : public dsf::sim::Block, public ForceAndMoment, public MassInterface
{
public:
	static Block *block;

	void configure(dsf::xml::xmlnode n);

	//
	//	should be able to make a generic aggregate() function that takes a vec and a fptr, and returns the summed force
	//	look at TFunctor, copy and add a return type. might be tricky if we descend multiple branches of tree eventually
	//	for now it's flat should not need to recurse.
	//			dsf::util::TFunctor<Block>(simulation, &Block::init);


	dsf::util::Vec3 force()  
	{/*
		Vec3 force(0,0,0);
		for (int i = 0; i < force_moment.size(); i++)
		{
			force += force_moment[i]->force();
		}
		return force;
		*/
		Vec3 force = aggregate<ForceAndMoment, Vec3>(force_moment, &ForceAndMoment::force);
		return force;
	}

	dsf::util::Vec3 moment() 
	{
		Vec3 moment(0,0,0);
		for (int i = 0; i < force_moment.size(); i++)
		{
			moment += force_moment[i]->moment();
		}
		return moment;
	};

	dsf::util::Mat3 MOI() 
	{ 
		Mat3 I;
		for (int i = 0; i < mass_interface.size(); i++)
		{
			I += mass_interface[i]->MOI();
		}
		return I;
	};
	double m()			 
	{
		double _m = 0.;
		for (int i = 0; i < mass_interface.size(); i++)
		{
			_m += mass_interface[i]->m();
		}
		return _m; 
	};

	std::vector< ForceAndMoment*> force_moment;
	std::vector< MassInterface* > mass_interface;
};
