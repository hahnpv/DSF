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

	dsf::util::Vec3 force()
	{
		return aggregate<ForceAndMoment, Vec3>(force_moment, &ForceAndMoment::force);
	}

	dsf::util::Vec3 moment()
	{
                return aggregate<ForceAndMoment, Vec3>(force_moment, &ForceAndMoment::moment);
	};

	dsf::util::Mat3 MOI()
	{
		return aggregate<MassInterface, Mat3>(mass_interface, &MassInterface::MOI);
	};
	double m()
	{
		return aggregate<MassInterface, double>(mass_interface, &MassInterface::m);
	};

	std::vector< ForceAndMoment*> force_moment;
	std::vector< MassInterface* > mass_interface;
};
