#include <cmath>
#include <iomanip>

#include "OblateEarth.h"
#include "sim/output.h"

#include "sim/TRefDict.h"
#include "util/math/constants.h"
#include "simpleguidance.h"

#include "util/tbl/tbl.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"

#include "AeroBase.h"
#include "AtmosBase.h"
#include "MassBase.h"

//test
#include "MissileFin.h"

using namespace std;
using namespace dsf::sim;
// using namespace dsf::vis;
using namespace dsf::util;
using namespace dsf::util::math;

Block* OblateEarth::block = TClass<OblateEarth,Block>::Instance()->getStatic();

OblateEarth::OblateEarth(void) 
{
	I(1,0,0, 0,1,0, 0,0,1);
}

void OblateEarth::configure(dsf::xml::xmlnode n)
{
	Block::configure( n);
	dsf::xml::xmlnode vehiclen = n.parent();
	std::string aeroblock  = (n = vehiclen).search("aero").attrAsString("id");
	std::string atmosblock = (n = vehiclen).parent().search("atmosphere").attrAsString("id");
	std::string earthblock = (n = vehiclen).parent().search("earth").attrAsString("id");

	rollingAirframe = (n = vehiclen).search("rbeom").attrAsBool("rollingAirframe");
	std::string frame = (n = vehiclen).search("rbeom").attrAsString("frame");

	aero  = TRefSim<Block,  AeroBase>(parent, aeroblock);
	atmos = TRefSim<Block, AtmosBase>(parent->getParent(), atmosblock);
	e     = TRefSim<Block,     WGS84>(parent->getParent(), earthblock);

	(n = vehiclen).search("rbeom");
	uvw   = n.attrAsVec3("velocity");
	euler = n.attrAsVec3("orientation");
	pqr   = n.attrAsVec3("rates");

	Vec3 uvw_0( uvw);

	n.search("position");
	p.lambda_d = n.attrAsDouble("lambda_d");
	p.l_i      = n.attrAsDouble("l_i");
	p.h        = n.attrAsDouble("h");

	cout << "using frame: " << frame << endl;
	if (frame.compare("inertial") == 0)
	{
		/// WRT Inertial Frame
		xyz   = e->InitXYZ(p);						// geodetic->inertial
		uvw   = e->T_b_i(euler,p).inv() * uvw;		// geodetic->inertial
		T_b_i = e->T_b_i(euler,p);					// generate
	}
	else if (frame.compare("earth") == 0)
	{
		/// WRT Earth Frame
		xyz   = e->InitXYZ(p);						// geodetic->inertial
		uvw   = e->T_b_i(euler,p).inv() * uvw_0 - e->w_e_i.skew() * xyz;		// earth->inertial
		T_b_i = e->T_b_i(euler,p);					// generate
		pqr  -= e->w_e_i;							// add earth rotation
	}
	else
	{
		cout << "INVALID FRAME OR NOT SPECIFIED! frame = " << frame << endl;
		cin.get();
	}

        cout << "lla: " << p.lambda_d << " " << p.l_i << " " << p.h << endl;
        cout << "euler: " << euler << endl;
	cout << "xyz: " << xyz << endl;
	cout << "uvw: " << uvw << endl;
	cout << "pqr: " << pqr << endl;
	cout << "eul: " << euler << endl;
	cout << "rolling airframe?: " << rollingAirframe << endl;
	cout << "frame: " << frame << endl;
//	cin.get();

	if (rollingAirframe)
	{
		omega = pqr.x;
		pqr.x = 0.;
	}

	xyz_0 = xyz;

	// init for guidance
	pqr_b = pqr;
	euler = e->euler(T_b_i, p);
	xyz_d = e->T_d_i(p) * xyz + Vec3(0,0,p.R_0);

}

void OblateEarth::init(void) 
{
	// integrator resolution
	TClassIntegrandDict<Block>::Instance()->add(TClass<OblateEarth,Block>::Instance(), xyz, dxdydz);
	TClassIntegrandDict<Block>::Instance()->add(TClass<OblateEarth,Block>::Instance(), uvw, dudvdw);
	TClassIntegrandDict<Block>::Instance()->add(TClass<OblateEarth,Block>::Instance(), pqr, dpdqdr);
	TClassIntegrandDict<Block>::Instance()->add(TClass<OblateEarth,Block>::Instance(), T_b_i, dT_b_i);
	if (rollingAirframe)
		TClassIntegrandDict<Block>::Instance()->add(TClass<OblateEarth,Block>::Instance(), omega, domega);

	// i/o resolution
	// need to group by some reference # or have a dict that points to unique class instantiation
	// so that the data is grouped by vehicle. Right now spits out by type ...
	o->add(p.h,		"Altitude",		"m");
	o->add(xyz_e,		"Earth XYZ",		"m");
//	o->add(xyz_d,		"XYZ (geodetic)",	"m");
//	o->add(uvw,			"Velocity",			"m/s");
	o->add(uvw_b,		"Velocity; Body",	"m/s");
	o->add(p.l_i,		"Longitude",		"rad");
	o->add(p.l_i_earth,	"Earth Longitude",	"rad");
	o->add(p.lambda_d,	"Latitude",		"rad");
//	o->add(dudvdw,      "Acceleration",     "m/s^2");
}

void OblateEarth::update(void) 
{
	pqr_b = pqr;
	euler = e->euler(T_b_i, p);
	xyz_d = e->T_d_i(p) * xyz + Vec3(0,0,p.R_0);
	xyz_e = Mat3(1,0,0,0,1,0,0,0,-1) 
		* Mat3(0,0,1, 0,1,0, 1,0,0) *((e->T_e_i(e->w_e_i[2] * t()) * xyz) // may not be necessary
		- xyz_0);	// quasi-NED

	if ( p.h < 0) end();

	if (rollingAirframe)
	{
		pqr[0] = 0.;
		pqr_b += Vec3(omega,0,0);
	}

	T_b_i += (I - T_b_i*T_b_i.inv()) * 0.5 * T_b_i;					/// DCM Orthogonalization

	uvw_b = T_b_i * (uvw + e->w_e_i.skew()*xyz);					// Calculate body velocity from inertial
//	uvw_b = T_b_i * uvw;											// Calculate body velocity from inertial

	atmos->update(p.h,uvw_b);
	aero->update(atmos->Mach(), atmos->rho(), uvw_b, pqr_b);
	e->calculate(xyz, t(), p);

	/// Forces
	ForceAndMoment * f = dynamic_cast<ForceAndMoment*>( parent);
	Vec3 forces  = f->force();
	Vec3 moments = f->moment();

	/// Mass Properties
	MassInterface * mi = dynamic_cast<MassInterface*>( parent);
	Mat3 MOI = mi->MOI();
	double m = mi->m();

	dT_b_i = pqr.skew() * T_b_i;									/// Update Derivatives
	dxdydz = uvw;
	dudvdw = T_b_i.inv() * forces * (1./m) + e->T_g_i(p).inv() * e->gravity(xyz, p);
	dpdqdr = (MOI.inv() * pqr.skew() * MOI) * pqr + MOI.inv() * moments;

	if (rollingAirframe) 
	{
		domega    = (1/MOI[0][0])*moments[0];
		dpdqdr[0] = 0;
		dpdqdr[1] = (1/MOI[1][1])*(-MOI[0][0]*omega*pqr[2] + moments[1]);
		dpdqdr[2] = (1/MOI[2][2])*( MOI[0][0]*omega*pqr[1] + moments[2]);
	}
}

void OblateEarth::rpt(void)
{
	cout << setw(7) << setprecision(7);
	cout << endl << "time: " << t() << endl;
	cout << "Latitude:  " << p.lambda_d << endl;
	cout << "Longitude (inertial): " << p.l_i << endl;
	cout << "Longitude (wrtearth): " << p.l_i_earth << endl;
	cout << "Altitude:  " << p.h << endl;
	cout << "Inertial Position: " << xyz << endl;

	double lambda_d = 0.;
	double l_i = 0.;
	Mat3 T_di(	-sin(lambda_d)*cos(l_i), -sin(lambda_d)*sin(l_i), cos(lambda_d),
							      -sin(l_i),		cos(l_i), 					  0,
					-cos(lambda_d)*cos(l_i), -cos(lambda_d)*sin(l_i), -sin(lambda_d) );

//	cout << "wrt. t=0:          " << T_di * (xyz - xyz_0 + e->w_e_i.skew() * xyz * t()) << endl; 
	cout << "wrt. t=0:          " << T_di * (e->T_e_i( (e->w_e_i[2] * t()) ) * xyz - xyz_0) << endl; 
	cout << "Quasi-FlatEarth:   " <<  xyz + e->w_e_i.skew() * xyz * t() - xyz_0 << endl;	// only makes sense for short engagement
//	cout << "Geodetic Position: " << e->T_d_i(p) * (xyz - xyz_0 + e->w_e_i.skew() * xyz * t()) << endl;		// good for bullet (since no rot)
	cout << "xyz_e:   " << xyz_e << endl;
	cout << "Earth Frame?:      " << e->T_e_i((e->w_e_i[2] * t())) * xyz << endl;
	cout << "Earth Frame:       " << e->T_e_i(p.l_i_earth - p.l_i) * xyz << endl;
	cout << "xyz_d:   " << xyz_d << endl;														// good for sat
	cout << "xyz_g:   " << e->T_d_g(p).inv() * xyz_d << endl;	
	cout << "xyz_d_0: " << e->T_d_g(p).inv() * e->T_d_i(p) * (xyz -xyz_0) << endl;

	cout << "Inertial Velocity:  " << uvw.mag() << endl;
	cout << "Body Velocity:      " << uvw_b.mag() << endl;
	cout << "pqr:   " << pqr_b << endl;
	cout << "euler: " << euler << endl;
}

void OblateEarth::finalize() 
{
}
