
#include "netmon.h"
#include "data.h"
#include "../../simulation/rbeq.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* netmon::block = TClass<netmon,Block>::Instance()->getStatic();

void netmon::rpt()
{
	data d;

	d.x = rbeq->position().x;
	d.y = rbeq->position().y;
	d.z = rbeq->position().z;

	d.phi   = rbeq->Orientation().x;
	d.theta = rbeq->Orientation().y;
	d.psi   = rbeq->Orientation().z;

	d.t = t();

	net->send<data>(d);
}