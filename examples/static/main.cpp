#include <time.h>

#include "sim/sim.h"

#include "../sixdof/vehicle.h"
#include "../sixdof/AeroBase.h"
#include "../sixdof/OblateEarth.h"
#include "../sixdof/MassBase.h"
#include "../sixdof/wgs84.h"
using namespace dsf::sim;

int main(int argc, char *argv[])
{
	// FIXME: staticly created simulation
	// FIXME: you can't currently do this!

		// Create simulation
	double dt = 0.1;		// seconds
	double tmax = 86400;		// seconds
	double rateConsole = 100;	// seconds
	double rateFile    =  10;	// seconds
	Block * root = new Block;

		// Instantiate simulation
	Sim *sim = new Sim();
	sim->load(root, dt, tmax, rateConsole, rateFile);
	sim->run();

	return 0;
}

/*
Root node: xmlRoot
 node: sim
  dt 0.1
  tmax 86400
  file 10.0
  library ./examples/sixdof/libsixdofsrc.so
  node: vehicle
   name Satellite
   id Vehicle
   node: rbeom
    id OblateEarth
    rollingAirframe false
    rpt 10.0
    frame earth
    orientation 0.,0.,0. orientation
    velocity 0.,7905.141346,0. velocity
    rates 0.,0.,0. rates
    node: position
     lambda_d 0
     l_i 0
     h 6378500
   node: aero
    id AeroBase
   node: mass
    id Mass
    mass 50000 mass
    area 1.0 area
    MOI 1,0,0,0,1,0,0,0,1 MOI
  node: atmosphere
   id Atmosphere
  node: earth
   id WGS84
*/
