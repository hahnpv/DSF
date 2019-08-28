#include <cmath>
#include <iomanip>
#include "bouncy.h"
#include "sim/output.h"
#include "sim/TRefDict.h"
#include "util/math/constants.h"

using namespace std;
using namespace dsf::sim;
using namespace dsf::util;
using namespace dsf::util::math;

Block * Bouncy::block = TClass<Bouncy,Block>::Instance()->getStatic();

Bouncy::Bouncy(void) 
{}

void Bouncy::init(void) 
{
		// integrator resolution
	TClassIntegrandDict<Block>::Instance()->add(TClass<Bouncy,Block>::Instance(), xyz, dxdydz);
	TClassIntegrandDict<Block>::Instance()->add(TClass<Bouncy,Block>::Instance(), uvw, dudvdw);

	orient = Vec3(0,0,0);

	o->add(xyz,		"Position",		"m");
	o->add(orient,	"Orientation","m/s");		// vis requires a orientation, even if dummy
	o->add(uvw,		"Velocity",		"m/s");
}

void Bouncy::configure(dsf::xml::xmlnode n)
{
	Block::configure( n);
	m   = n.attrAsDouble("mass");
	e   = n.attrAsDouble("e");
    g   = n.attrAsVec3("g");
    xyz = n.attrAsVec3("xyz");
    uvw = n.attrAsVec3("uvw");
}

void Bouncy::update(void) 
{	
	dxdydz = uvw;																// position kinematics
	dudvdw =   g;																// translation dynamics 

	// bounce dynamics
	if(xyz.z <= 0 && uvw.z < 0)
	{
		xyz.z = 0.;
		uvw.z = -uvw.z * e;
	}
	if ( xyz.z == 0. && uvw.z < 0.2) end();
}


void Bouncy::rpt(void)
{
	if (sample(0.1))
	{
		cout << "time " << t() << endl;
		cout << "xyz: " << xyz << endl;
		cout << "uvw: " << uvw << endl;
	}
}

void Bouncy::finalize() 
{
	cout << endl;
	cout << "xyz: " << xyz << endl;
	cout << "uvw: " << uvw << endl;
}
