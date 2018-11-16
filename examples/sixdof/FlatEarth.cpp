#include <cmath>
#include <iomanip>
#include "FlatEarth.h"
#include "simpleguidance.h"
#include "sim/output.h"
#include "sim/TRefDict.h"
#include "util/math/constants.h"

#include "AeroBase.h"
#include "AtmosBase.h"
#include "MassBase.h"

using namespace std;
using namespace dsf::sim;
using namespace dsf::util;
using namespace dsf::util::math;

Block * FlatEarth::block = TClass<FlatEarth, Block>::Instance()->getStatic();

FlatEarth::FlatEarth(void) 
{}

void FlatEarth::init(void) 
{
		// integrator resolution
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), xyz, dxdydz);
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), uvw, dudvdw);
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), pqr, dpdqdr);
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), q0, dq0);
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), q1, dq1);
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), q2, dq2);
	TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), q3, dq3);
	if (rollingAirframe)
		TClassIntegrandDict<Block>::Instance()->add(TClass<FlatEarth,Block>::Instance(), omega, domega);

	g (0, 0, 9.801);
}

void FlatEarth::configure(dsf::xml::xmlnode n)
{
	Block::configure( n);

	cout << "FlatEarth::configure" << endl;

	dsf::xml::xmlnode vehiclen = n.parent();
	std::string aeroblock  = (n = vehiclen).search("aero").attrAsString("id");
	std::string atmosblock = (n = vehiclen).parent().search("atmosphere").attrAsString("id");
	rollingAirframe = (n = vehiclen).search("rbeom").attrAsBool("rollingAirframe");

	atmos = TRefSim<Block,		AtmosBase>(parent, atmosblock);
	aero  = TRefSim<Block,		 AeroBase>(parent, aeroblock);

	(n = vehiclen).search("rbeom");
	xyz   = n.attrAsVec3("position");
	uvw   = n.attrAsVec3("velocity");
	euler = n.attrAsVec3("orientation");
	pqr   = n.attrAsVec3("rates");

	double phi   = euler.x;
	double theta = euler.y;
	double psi   = euler.z;

	q0 = cos(psi/2)*cos(theta/2)*cos(phi/2) + sin(psi/2)*sin(theta/2)*sin(phi/2);
	q1 = cos(psi/2)*cos(theta/2)*sin(phi/2) - sin(psi/2)*sin(theta/2)*cos(phi/2);
	q2 = cos(psi/2)*sin(theta/2)*cos(phi/2) + sin(psi/2)*cos(theta/2)*sin(phi/2);
	q3 = sin(psi/2)*cos(theta/2)*cos(phi/2) - cos(psi/2)*sin(theta/2)*sin(phi/2);

	cout << "xyz: " << xyz << endl;
	cout << "uvw: " << uvw << endl;
	cout << "pqr: " << pqr << endl;
	cout << "eul: " << euler << endl;
//	cin.get();

	if (rollingAirframe)
	{
		omega = pqr.x;
		pqr.x = 0.;
	}
}

void FlatEarth::update_matrices(void) 
{
	normalize();

	T_e_b(	q0*q0 + q1*q1 -q2*q2 - q3*q3, 2*(q1*q2 - q0*q3),			 2*(q1*q3 + q0*q2),
			2*(q1*q2 + q0*q3),			  q0*q0 - q1*q1 + q2*q2 - q3*q3, 2*(q2*q3 - q0*q1),
			2*(q1*q3 - q0*q2),			  2*(q2*q3 + q0*q1),			 q0*q0 - q1*q1 - q2*q2 + q3*q3 );

	euler.x = atan2( 2.*(q2*q3 + q0*q1) , (q0*q0 - q1*q1 - q2*q2 + q3*q3) );
	euler.y = asin( -2.*(q1*q3 - q0*q2) );
	euler.z = atan2( 2.*(q1*q2 + q0*q3) , (q0*q0 + q1*q1 - q2*q2 - q3*q3) );
}

void FlatEarth::update(void) 
{	
	pqr_b = pqr;

	if (rollingAirframe)
	{
		pqr[0] = 0.;
		pqr_b += Vec3(omega,0,0);
	}

	update_matrices();

	atmos->update(-xyz.z, uvw);
	aero->update(atmos->Mach(), atmos->rho(), uvw, pqr_b);

//	Vec3 forces  = aero->force()  + gnc->force();
//	Vec3 moments = aero->moment() + gnc->moment();
	
	/// Forces
	ForceAndMoment * f = dynamic_cast<ForceAndMoment*>( parent);
	Vec3 forces  = f->force();
	Vec3 moments = f->moment();

	/// Mass Properties
	MassInterface * mi = dynamic_cast<MassInterface*>( parent);
	Mat3 MOI = mi->MOI();
	double m = mi->m();

	g_b    = T_e_b.inv() * g;													// gravity	
	dxdydz = T_e_b * uvw;														// position kinematics
	dudvdw = pqr.skew() * uvw + (forces)*(1./m) + g_b;							// translation dynamics 
	dpdqdr = MOI.inv()*pqr.skew()*MOI*pqr + MOI.inv()*moments;					// rotation dynamics

	dq0 = 0.5*(		   0 - pqr.x*q1 - pqr.y*q2 - pqr.z*q3);
	dq1 = 0.5*( pqr.x*q0 +		  0 + pqr.z*q2 - pqr.y*q3);
	dq2 = 0.5*( pqr.y*q0 - pqr.z*q1 +		 0 + pqr.x*q3);
	dq3 = 0.5*( pqr.z*q0 + pqr.y*q1 - pqr.x*q2 +		0);

	if (rollingAirframe) 					// no-roll body frame, presumes just Ixx Iyy Izz no cross inertia terms
	{
		domega    = (1/MOI[0][0])*moments[0];
		dpdqdr[0] = 0;
		dpdqdr[1] = (1/MOI[1][1])*(-MOI[0][0]*omega*pqr[2] + moments[1]);
		dpdqdr[2] = (1/MOI[2][2])*( MOI[0][0]*omega*pqr[1] + moments[2]);
	}
/*	g_b    = T_e_b.inv() * g;																	// gravity	
	dxdydz = T_e_b * uvw;																		// position kinematics
	dudvdw = pqr.skew() * uvw + (forces)*(1/mass->m()) + g_b;									// translation dynamics 
	dpdqdr = mass->MOI().inv()*pqr.skew()*mass->MOI()*pqr + mass->MOI().inv()*(moments);		// rotation dynamics

	dq0 = 0.5*(		   0 - pqr.x*q1 - pqr.y*q2 - pqr.z*q3);
	dq1 = 0.5*( pqr.x*q0 +		  0 + pqr.z*q2 - pqr.y*q3);
	dq2 = 0.5*( pqr.y*q0 - pqr.z*q1 +		 0 + pqr.x*q3);
	dq3 = 0.5*( pqr.z*q0 + pqr.y*q1 - pqr.x*q2 +		0);

	if (rollingAirframe) 					// no-roll body frame, presumes just Ixx Iyy Izz no cross inertia terms
	{
		domega    = (1/mass->MOI()[0][0])*aero->moment()[0];
		dpdqdr[0] = 0;
		dpdqdr[1] = (1/mass->MOI()[1][1])*(-mass->MOI()[0][0]*omega*pqr[2] + aero->moment()[1]);
		dpdqdr[2] = (1/mass->MOI()[2][2])*( mass->MOI()[0][0]*omega*pqr[1] + aero->moment()[2]);
	}
	*/
}

	// replace with the lambda normalization from Zipfel
void FlatEarth::normalize(void)
{
	double n;
	n = sqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3);
	q0 /= n;
	q1 /= n;
	q2 /= n;
	q3 /= n;
}

void FlatEarth::rpt(void)
{
//	if (sample(0.1))
//	{
		cout << "time " << t() << endl;
		cout << "xyz: " << xyz << endl;
		cout << "uvw: " << uvw << endl;
		cout << "pqr: " << pqr << endl;
//	}
}

void FlatEarth::finalize() 
{
	cout << endl;
	cout << "xyz: " << xyz << endl;
	cout << "uvw: " << uvw << endl;
	cout << "pqr: " << pqr << "; " << omega << endl;
	cout << "results should be (according to CMD):" << endl;
	cout << "x: 1000.19   y: -5.88593   z: -999.808" << endl;
	cout << "p: 2421.66   q: -0.010464  r: -0.019505" << endl;
}
