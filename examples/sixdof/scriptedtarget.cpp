#include "scriptedtarget.h"
//#include "util/gauss.h"
#include "sim/output.h"

#include "sim/TRefDict.h"
#include "util/math/constants.h"
#include "EarthBase.h"

using namespace dsf::util;
using namespace dsf::sim;			// TClass

Block * ScriptedTarget::block = TClass<ScriptedTarget,Block>::Instance()->getStatic();

void ScriptedTarget::init(void) 
{
	o->add(xyz,"TargetXYZ","m");
}

void ScriptedTarget::configure(dsf::xml::xmlnode n)
{
	Block::configure( n);
	cout << "ScriptedTarget::configure" << endl;
	cout << "reporting every " << rptRate << endl;
	std::string filename = n.attrAsString("filename");
	error = n.attrAsBool("error");

//	std::string target = "SixDOF";//n.attrAsString("target");
	n.parent();
	n.search("rbeom");
	std::string target = n.attrAsString("id");

	cout << "target: " << target << endl;
//	cin.get();
	rbeq = TRefSim<Block, EarthBase>( parent, target);
	// changed target to GuidedBullet instead of 6DOF. Now find GuidedBullet, traverse down to rbeq,
	// get id and cast that.
	cout << "using filename: " << filename << endl;
	MortarXTab = Table(filename,"[MortarX]");
	MortarYTab = Table(filename,"[MortarY]");
	MortarZTab = Table(filename,"[MortarZ]");
//	cin.get();

	mortarTime = 0.;
	xyz_err(0,0,0);
	stdev = 0.;
	mean = 0.;
	NMDold = -1.;							/// prevents premature exit during the first iteration
}

void ScriptedTarget::update(void) 
{
	if ( sample() )
	{
		xyz.x = MortarXTab( t() + mortarTime );
		xyz.y = MortarYTab( t() + mortarTime );
		xyz.z = MortarZTab( t() + mortarTime );

		Vec3 nmd = xyz - rbeq->position();
		NMDold = NMD;
		NMD = abs(nmd.mag());
	/*	if(error) {
			xyz_err.x = get_gauss(0,stdev);
			xyz_err.y = get_gauss(0,stdev);
			xyz_err.z = get_gauss(0,stdev);
		}*/
	}

	// if NMD < 20, increase integration rate; dt = 0.000001
	double new_dt = 0.000001;
	if ( (NMD < /*20*/ 40) && ( dt() > new_dt) )
	{
		set_dt(	new_dt);
	}
	// if NMDold < NMD, we've achieved closest approach. Terminate sim.
	if ( (NMDold < NMD) && NMDold > 0.)// && sample() )
	{
		cout << "closest approach exceeded; time = " << t() << endl;
//		cin.get();
		end();
	}

	// this model may not, and probably is not, the appropriate place to track NMD, since
	// its the NMD from the rbeq model's perspective and we may be tracking multiple engagements etc.
	// think about design.
	// might also be a third class that regulates sim f(nmd).
}

Vec3 ScriptedTarget::Position(double t)				/// Accessor for guidance models. Uses static corruption for a given time
{
	Vec3 position;

	position.x = MortarXTab( t + mortarTime );
	position.y = MortarYTab( t + mortarTime );
	position.z = MortarZTab( t + mortarTime );

	position += xyz_err;
	return position;
};

void ScriptedTarget::rpt(void) 
{
	cout << "[target] NMD: " << NMD << "\t" << xyz << endl;//"\t" << rbeq->position() << endl;
}

void ScriptedTarget::finalize(void) 
{
	cout << "[target][time]: " << t() << endl;
	cout << "[target][xyz]:  " << MortarXTab(t()) << ", " 
				   << MortarYTab(t()) << ", "
				   << MortarYTab(t()) << endl; 
}
