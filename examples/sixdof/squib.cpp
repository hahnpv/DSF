#include <cmath>
#include <iomanip>
#include "squib.h"
#include <ctime>


#include "util/gauss.h"
#include "util/math/constants.h"

using namespace std;
using namespace dsf::util::math;

Squib::Squib(double pulse_force_angle, double sl, int squib_number, bool dudcheck, bool thrustcoeff) 
{
	this->pulse_force_angle = pulse_force_angle;
	this->squib_number		= squib_number;
	this->sl				= sl;
	this->dudcheck			= dudcheck;
	this->thrustcoeff		= thrustcoeff;
}

void Squib::init(void) 
{
	// set the seed
//	srand( (unsigned)time(NULL) );

	if ( pulse_force_angle >= PI )
		pulse_force_angle -= 2*PI;

	squib_state = 0;

	XYZ (0, 0, 0);
	LMN (0, 0, 0);

	char *fname = "config/6dofSquibPack.dat";
	ThrustProfile = new dsf::util::Table(fname,"[ThrustProfile]");

	dud    = false;
	c_star = 1;

	firing = false;
	squib_stat = true;

	cout << "Squib: " 		<< squib_number;
	cout << " pulse_force_angle: "  << pulse_force_angle;
	cout << " stationline: " << sl << endl;
	cout << " dudcheck: " << dudcheck << "\tthrustcoeff: " << thrustcoeff << endl;

}

void Squib::update(double t, bool safe_sample) 
{
	if ( squib_state == 0) 
	{
		squib_state = 1;
		squib_stat  = false;

/*		// generate a positive gauss number
		int rnd_number;
		while ( (rnd_number = get_gauss(0.0001)) < 0)		// tenth of a msec
		{}	// loop until a positive value is found
		cout << "rnd_number: " << rnd_number << endl;

*/		//

//		cout << " FIRING TIME DELAY!!! " << endl;
		firing_time = t;// + rnd_number;		// **should** delay squibs firing, do a few runs and confirm
//		cout << "squib_state: " << squib_state << endl;
		cout << "SQUIB " << squib_number << " FIRING: t=" << setw(7) << setprecision(6) << t << endl;

		// do the dud check
/*		// do a straight roll, 25% fail rate.	
		if (dudcheck) 
		{
			double check = dsf::util::getUniform(1,100);
			cout << "check = " << check << endl;
			if (check < 10.0) 
			{
				cout << "Squib is a dud ... no fire. Squib = " << squib_number << endl;
				dud = true;			// not necessary except for logging purposes later
				squib_state++;
				firing = false;
				
			}
		}
*/
		// calculate thrust coefficient if we are using that method
/*		if (thrustcoeff) 
		{
			c_star = 0.90 + dsf::util::get_gauss(0.,0.10);		// should result in numbers between 1.0 and 0.8, centering at 0.9.
			cout << "c_star = " << c_star << endl;
		}
*/

	} 
	else if ( squib_state == 1 && safe_sample ) 	// fire squib.
	{

		thrust = ThrustProfile->interp(t - firing_time);		

		XYZ.x = 0;
		XYZ.y = c_star * thrust * cos( pulse_force_angle );
		XYZ.z = c_star * thrust * sin( pulse_force_angle );

		LMN.x = 0;			
		LMN.y = -sl * XYZ.y;
		LMN.z =  sl * XYZ.z;

		if ( thrust == -1) 
		{
			XYZ (0, 0, 0);
			LMN (0, 0, 0);
			squib_state++;
			firing = false;
		}
	}
}