#include "simpleguidance.h"
#include "linear.h"
#include "squib.h"
#include "FlatEarth.h"
#include "scriptedtarget.h"
#include "sim/TRefDict.h"

#include <sstream>
#include <string>
#include <cstdlib>
#include <ctime>
#include <iostream>
#include <time.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/timeb.h>
#include <string.h>
#include "util/math/constants.h"

using namespace std;
using namespace dsf::util;
using namespace dsf::util::math;
using namespace dsf::sim;

Block * SimpleGuidance::block = TClass<SimpleGuidance,Block>::Instance()->getStatic();

SimpleGuidance::SimpleGuidance(void) 
{}

void SimpleGuidance::init(void) 
{
//	LinearModel = new Linear(data->get_DS(), data->get_updateint(), data->get_SF());
//	LinearModel = new Linear(1, 500, 40000);
	LinearModel = new Linear(1, 500, 40000);

	state_0	   = 1.0;	// initial unmodified state var
	state 	   = 1.0;	// data->get_squib_start_time();
	wait  	   = 0.05;	// data->get_squib_delay();
	stateError = 0.0;	// data->get_state_error();
	phaseError = 0.0;	// data->get_phase_error();

	numSquibsFired   = 0;		// counts squibs fired;
	squib_dt = 0.0000001;		// increased integration fidelity during a squib event

	// set the random seed (apparently not available in Windows)
//	srand( runNumber );		// lame ...

		// Random draw for random phase bias
//	gaussPhaseBias = get_gauss(0.25,0.25);		// usethisforthat one performance run
//	cout << "gaussPhaseBias: " << gaussPhaseBias << endl;

	// new, think tables are bad though
	pwt.push_back( new Table("config/pwt-0.005.dat","[PhaseWarp]") );	
	pwt.push_back( new Table("config/pwt-0.015.dat","[PhaseWarp]") );	
	pwt.push_back( new Table("config/pwt-0.025.dat","[PhaseWarp]") );	

	// make squibs 
	numSquibs = 30;
	int j = numSquibs/3;
	int k = 1;

	bool dud = false; // (bool)data->get_dud_check();
	bool ct  = false; // (bool)data->get_ct_check();

	cout << "instantiating squibs" << endl;

	for (int i=1; i<=10; i++) 													// Create individual squib objects
	{
		double angle = ((2*PI)/j)*i;
		/// angle / stationline / number / dudflag / thrustcoeff flag
		SquibPack.push_back( new Squib( angle, 0.005, k, dud, ct));				///< squb row sl = 0.005
		k++;
		SquibPack.push_back( new Squib(	angle, 0.015, k, dud, ct));				///< squb row sl = 0.015
		k++;
		SquibPack.push_back( new Squib( angle, 0.025, k, dud, ct));				///< squb row sl = 0.025
		k++;
	}

	// Initialize squibs
	for (squib_iter = SquibPack.begin(); squib_iter != SquibPack.end(); squib_iter++)
		(*squib_iter)->init();
}

void SimpleGuidance::configure(dsf::xml::xmlnode n)
{
	Block::configure( n);
	cout << "SimpleGuidance::configure" << endl;
	
	n.search("guidance");
	cout << "Guidance model: " << n.attrAsString("id");		
	n.parent();
	
	n.search("rbeom");
	std::string rbmodel = n.attrAsString("id");
	cout << "rigid body model: " << rbmodel << endl;
	rbeq = TRefSim<Block, EarthBase>(parent, rbmodel);
	target_model = TRefSim<Block, ScriptedTarget>(parent, "ScriptedTarget");			// need to un-hardcode
}

void SimpleGuidance::update(void) 
{
	if ( t() >= state_0 && sample(0.05) && sample() ) {	// Get updates from the linear model AT THE SAME RATE of squib fire ...
//	if ( sample(0.1) && sample()  )  {
		cout << "Updating linearized guidance model " << t() << endl;
		// get state information from the 6DOF
		Vec3 xyz = rbeq->position();
		Vec3 uvw = rbeq->velocity();
		Vec3 pqr = rbeq->rotvelocity();
		Vec3 orientation = rbeq->Orientation();

		cout << "using: " << endl
			 << "xyz: " << xyz << endl
			 << "uvw: " << uvw << endl
			 << "pqr: " << pqr << endl
			 << "eul: " << orientation << endl;

		// if using error model, apply errors
//		if (stateError) {
/*			xyz.x += get_gauss(10);		// m
			xyz.y += get_gauss(10);		// m
			xyz.z += get_gauss(10);		// m

			uvw.x += get_gauss(5);		// m/s
			uvw.y += get_gauss(.1);		// m/s
			uvw.z += get_gauss(.1);		// m/s

			orientation.x += get_gauss(1);	// rad
			orientation.y += get_gauss(.01);// rad
			orientation.z += get_gauss(.01);// rad

			pqr.x += get_gauss(.01);	// rad/s
			pqr.y += get_gauss(.001);	// rad/s
			pqr.z += get_gauss(.001);	// rad/s
*/
//		}

		// Trade Study - apply constants to certain parameters.

		// Get a map of data from the linearized model
//		if ( force().mag() != 0 )	 	// then a squib is firing during our prediction attempt (has yet to happen)
//		{
//			cout << "!!! SQUIB IS FIRING DURING PREDICTION ATTEMPT!! Skip Prediction ..." << endl;
//		} else 
//		{
			LinearizedModel.clear();
			LinearizedModel = LinearModel->update(xyz, uvw, pqr, orientation, t() );
//		}

		double lastnmd = 1000*1000 + 5*5 + 1000*1000;		// a big number to start iterating with, ~NMD^2

		cout << "linear model size: " << LinearizedModel.size() << endl;
		map<Vec3,double>::const_iterator iter;
		for (iter=LinearizedModel.begin(); iter != LinearizedModel.end(); ++iter) 
		{
			xyz_err = target_model->Position(iter->second) - iter->first;		// find the distance between us and them 
			if (xyz_err.mag() > lastnmd) 										// last data point was the closest approach
			{
				iter--;																// back up
				xyz_err = target_model->Position(iter->second) - iter->first;		// get the real data points
				time 	= iter->second;

				cout << endl;
				cout << "[gnc][xyz] " 	   << iter->first 	<< "\t[t] " << time << endl; 
				cout << "[gnc][target] "   << target_model->Position(iter->second) << endl;
				cout << endl;
			
				iter = LinearizedModel.end();		// fast forward to the last data point  
				iter--;								// rewind once, so we increment to end next loop (otherwise crash)
			}

			lastnmd = xyz_err.mag();
		}

//		xyz_err[0] = 0;				// by definition. We can't divert in the x direction so don't try to.

		/// Calculate phase and magnitude
		xyz_body  = rbeq->_Teb().inv() * xyz_err;
		phase     = atan2( xyz_body.z, xyz_body.y );
		magnitude = sqrt( pow( xyz_body.y, 2 ) + pow( xyz_body.z, 2 ) );	

		cout << "Magnitude: " << magnitude << endl;
		cout << "Phase:     " << phase     << endl;
		cout << "from:      " << xyz_body  << endl;
	}

	///	Add a bias to the phase
	// should be += trying the mirror 
//	phase -= gaussPhaseBias;

	// if using error model, apply error to phase 
	if (phaseError) 
	{
		cout << "using phase corruption" << endl;
//		double error = get_gauss((double)90.0);
//		phase += (error/57.295); // rad
	}

	// 
	//	Squib Space
	//
	bool searching = false;
	if (	sample()
//		&& 	( magnitude >= (0.127 * (time - State::t))/1.495 )		// real squibs, 	0.127 N/s * 30 = 3.81 N/s (0.08495)
		&&	( magnitude >= (0.1 * (time - t() )))					// linear fit to try and control when squibs fire
		&&	( state <= t() ) 	
		&& 	( numSquibsFired < numSquibs ) )						// real squibs, 30
	{
		searching = true;
		if (dt() > squib_dt)
		{
			//	this messes up predictions. not sure why.
		//	set_dt( squib_dt);
		}
		
		// Explicity Schedule Next Integration
		// State::sample(State::EVENT, State::t + squib_dt);
		//	std::cout << " I should be explicity scheduling an integration" << std::endl;
		//	clock->set_dt(squib_dt);

		// Check all squibs for in-line-ness
//		double p = rbeq->rotvelocity().x;		// was:rot_Rate()
		double p = rbeq->Orientation().x;
		double squibphase;
		for (squib_iter = SquibPack.begin(); squib_iter != SquibPack.end(); squib_iter++) 
		{
			squibphase  = phase - (*squib_iter)->get_pulse_force_angle();			// find phase position of squib
			squibphase -= 2*3.14159*floor( squibphase/(2*3.14159));		// 0 .. 2PI

			int x;
			if ( (*squib_iter)->get_sl() == 0.005)			// 0.005
				x = 0;
			else if ((*squib_iter)->get_sl() == 0.015 )		// 0.015
				x = 1;
			else if ((*squib_iter)->get_sl() == 0.025 )		// 0.025
				x = 2;
			else 
				cout << "MATCH NOT FOUND!!! " << (*squib_iter)->get_sl() << endl;
			if ( (x == 0) || (x == 1) )
				squibphase -= pwt[x]->interp( squibphase * 57.295 ) / 57.295;			// Interpolate table
			squibphase -= 2*3.14159*floor( squibphase/(2*3.14159));		// 0 .. 2PI

//			if ( squibphase <= 0.00019025*p && squibphase >= 0.00018975*p && (*squib_iter)->status()) 
			if ( squibphase <= (p + 0.0125) && squibphase >= (p - 0.0125) && (*squib_iter)->status()) 
			{
				if ( (*squib_iter)->status() ) 
				{
					(*squib_iter)->set_squib();	// not yet fired, same pulse force angle
					squib_iter++;
					numSquibsFired++;	
				}

				set_state();				// Don't fire any more squibs for awhile
		//		set_dt( 0.0001);			// reinstate old dt
				break;						// end loop
			}
		}
	}

	// Continue firing squibs each iteration (probably would be faster to use [i] notation, i<numSquibs, for optimization) ... check w/gprof) 
	int num_squibs_firing = 0;
	for (squib_iter = SquibPack.begin(); squib_iter != SquibPack.end(); squib_iter++) {
		if ( (*squib_iter)->firing_bit() ) {
			(*squib_iter)->update(t(),sample());
			num_squibs_firing++;
			// Explicity Schedule Next Integration
			// State::sample(State::EVENT, State::t + squib_dt);
			if (dt() > squib_dt)
			{
			//	cout << "setting dt = " << squib_dt << endl;
				set_dt( squib_dt);
			}
		}
	}


	// unset dt when no squibs are firing
//	if (num_squibs_firing == 0 && dt() <= squib_dt && state > t() )
	if (num_squibs_firing == 0 && dt() <= squib_dt && !searching )
	{
	//	cout << "dt: " << dt() << " setting regular dt" << endl;
		set_dt( 0.0001);
	}

}

void SimpleGuidance::rpt(void) 
{
/*
	if ( State::ticklast ) {

	string fname = "RandGunPoint";

//	ostringstream stream;
//	stream << x << flush;
//	fname.insert(10,stream.str());

	ofstream *fout = new ofstream(fname.c_str(), ios_base::app);

	// data->azimuth, position.x,position.y,position.z, time, NMD.
	*fout// 	<< data->get_theta() << "\t"
	//	<< data->get_psi() << "\t" 
	//	<< target_model->NearMiss() << "\t" 
		<< (runNumber + 0 ) / (180 / 3.1415926) << "\t"		// only applies to static target runs
		<< airframe->position().x << "\t"
		<< airframe->position().y << "\t"
		<< airframe->position().z << "\t"
	//	<< target_model->Position(State::t).x << "\t"
	//	<< target_model->Position(State::t).y << "\t"
	//	<< target_model->Position(State::t).z << "\t"
              	<<  endl;

	fout->close();

	SquibPack.clear();

	}
	*/
}

void SimpleGuidance::finalize(void)
{}