#include "atmosphere.h"
#include <cmath>

using namespace dsf::sim;
using namespace dsf::util;

Block* Atmosphere::block = TClass<Atmosphere,Block>::Instance()->getStatic();

Atmosphere::Atmosphere(void) {}

//void Atmosphere::init(void) {}

void Atmosphere::update(double alt, Vec3 uvw_b) 
{
	alt = abs(alt);
	if ( alt < 11000)	// Troposphere
	{
		Temp  = 15.04 - (0.00649 * abs(alt));						// temperature, celsius
		press = 101.29 * pow( ((Temp + 273.1)/ 288.08) , 5.256);	// pressure, kilopascal
	}
	else if ( alt < 25000)
	{
		Temp = -56.46;
		press = 22.65 * exp(1.73 - 0.000157 * alt);
	}
	else if ( alt >= 25000)
	{
		Temp = -131.21 + 0.00299 * alt;
		press = 2.488 * pow( (Temp + 273.1) / 216.6, -11.388);
	}
	else if ( alt >= 100000)		// presume the edge of space is here; hard change in vars, need to test reentry
	{
		Temp = -18.2;					// INCORRECT but keeps M number sane. Also discontinuous....
		press = 0.;						// leads to zero density. 
	}
	Rho   = press / (0.2869*(Temp+273.1));						// density, kg/m^3
	M     = uvw_b.mag() / sqrt(1.4*287*(Temp+273.1));			// velocity, m/s^2
}