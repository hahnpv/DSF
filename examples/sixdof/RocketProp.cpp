#include "RocketProp.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* RocketProp::block = TClass<RocketProp,Block>::Instance()->getStatic();

void RocketProp::configure(dsf::xml::xmlnode n)
{
	is_firing = false;
	Isp  = 0.;
	mdot = 0.;
	g_0 = 9.801;
	s_b(0,0,0);
}

void RocketProp::update()
{
	if (is_firing)
	{
		XYZ( mdot * g_0 * Isp, 0, 0);
		LMN = s_b.cross( XYZ);
	}
}