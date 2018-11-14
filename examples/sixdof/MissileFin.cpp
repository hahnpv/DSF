#include "MissileFin.h"

#include "EarthBase.h"
#include "sim/TRefDict.h"
#include "util/math/constants.h"

#include <cmath>

dsf::sim::Block* MissileFin::block = dsf::sim::TClass<MissileFin,Block>::Instance()->getStatic();

void MissileFin::configure(dsf::xml::xmlnode n) 
{
	cout << "MissileFin::configure" << endl;

	// for now, static testing configuration
	nfin = 4;
	fin.resize( nfin);
	for (int i = 0; i < nfin; i++)
	{
		fin[i].Cl    = 1.;
		fin[i].Cd0   = 0.5;
		fin[i].delta = 0.;
		fin[i].theta = ((double)i / (double)nfin) * 2. * dsf::util::math::PI;
		fin[i].sbf( 0., /*-0.25,*/ 0.05*cos( fin[i].theta ), 0.05*sin( fin[i].theta ) );
		fin[i].Tbf( 1.,					  0.,				   0.,
					0.,  cos( fin[i].theta ), -sin( fin[i].theta ),
					0., sin( fin[i].theta ), cos( fin[i].theta ));
	}

	for (int i = 0; i < nfin; i++)
	{
		cout << "fin " << i << endl;
		cout << "theta: " << fin[i].theta << endl;
		cout << "sbf:   " << fin[i].sbf   << endl;
		cout << "Tbf:   " << fin[i].Tbf   << endl;
	}
	
	std::string earthblock = "OblateEarth";
	earth = dsf::sim::TRefSim<dsf::sim::Block, EarthBase>(parent, earthblock);

	cin.get();
}

void MissileFin::update() 
{
//	if ( sample(0.1) )
//	{
		XYZ(0, 0, 0);
		LMN(0, 0, 0);

		for (int i = 0; i < nfin; i++)
		{
			fin[i].delta = -0.25;

			dsf::util::Vec3 force_f( fin[i].Cd0 + fin[i].Cl * fin[i].delta, 0., fin[i].Cl * fin[i].delta );
			XYZ  += fin[i].Tbf * force_f;
			LMN += fin[i].sbf.cross( fin[i].Tbf * force_f );

/*			cout << "fin " << i << endl
				 << " force_f: " << force_f << endl
				 << " force_b: " << fin[i].Tbf * force_f << " moment_b: " << fin[i].sbf.cross( fin[i].Tbf * force_f ) << endl;
*/		};

//		cout << "Combined force/moment: " << force << "; " << moment << endl;
//		cin.get();
//	}
}
