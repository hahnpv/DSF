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

	o->add(xyz,		"Position",		"m");
	o->add(uvw,		"Velocity",		"m/s");

	m = 1.0;
	e = 0.8;
	g (0, 0, -9.801);
}

void Bouncy::configure(dsf::xml::xmlnode n)
{
	/*
	Block::configure( n);

	cout << "Bouncy::configure" << endl;

	dsf::xml::xmlnode vehiclen = n.parent();
	std::string aeroblock  = (n = vehiclen).search("aero").attrAsString("id");
	std::string atmosblock = (n = vehiclen).search("atmosphere").attrAsString("id");
	rollingAirframe = (n = vehiclen).search("rbeom").attrAsBool("rollingAirframe");

	atmos = TRefSim<Block,		AtmosBase>(parent, atmosblock);
	aero  = TRefSim<Block,		 AeroBase>(parent, aeroblock);

	(n = vehiclen).search("rbeom");
	xyz   = n.attrAsVec3("position");
	uvw   = n.attrAsVec3("velocity");

	cout << "xyz: " << xyz << endl;
	cout << "uvw: " << uvw << endl;
	*/

	xyz = Vec3(0,0,10);
	uvw = Vec3(0,0, 0);
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
