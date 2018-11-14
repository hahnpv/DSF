#include "wgs84.h"
#include <cmath>
#include "util/sign.h"
//#include "util/math.h"

using namespace std;
using namespace dsf::sim;
using namespace dsf::util;
//using namespace dsf::util::math;

#define PI 3.1415926535897

template<typename T>
inline bool isnan(T value)
{
return value != value;
}

#include <limits>
template<typename T>
inline bool isinf(T value)
{
return std::numeric_limits<T>::has_infinity && (value == std::numeric_limits<T>::infinity());
}

Block* WGS84::block = TClass<WGS84,Block>::Instance()->getStatic();

WGS84::WGS84()
{
	a = 6378137.0;					///< Semi-major Axis
	f = (a - 6356752.31) / a;		///< Flattening Parameter

	GM    =  3.986005E14;			///< Gravitational Parameter, earth.
	C_2_0 = -4.841668E-4;			///< Gravitational Parameter, WGS84, earth.

	w_earth  = (2*PI)/86164.09054;	///< Sidereal rotation rate of the earth; rad/second
	w_e_i(0, 0, w_earth);			///< Sidereal rotation rate of the earth; wrt [I] frame, rad/second
}

void WGS84::calculate( Vec3 xyz, double t, Position &p) 
{
	p.lambda_c = asin( xyz.z / xyz.mag() );
	p.lambda_d = p.lambda_c;

	int i = 1;
	double lambda_d_old = 1;
	while ( abs(lambda_d_old - p.lambda_d) >= 10E-10 && i <=100) 
	{
		p.R_0 = a * ( 1 - (f/2) * (1 - cos( 2 * p.lambda_d ) + (( 5*pow(f,2) )/16)*(1-cos(4*p.lambda_d)))); 
		p.h = xyz.mag() - p.R_0;
		p.delta = f * sin(2 * p.lambda_d) * ( 1 - (f/2) - (p.h/p.R_0));
		lambda_d_old = p.lambda_d;
		p.lambda_d = p.lambda_c + p.delta;
		i++;
	}

	double t_0	= 0;								// sim start time, 0 by default but we may offset times later
	p.l_i		  = atan2(xyz.y, xyz.x); 
	p.l_i_earth   = p.l_i - w_earth * ( t - t_0 );			// think if we need l_g_0
	p.l_i        -= 2*PI*floor( p.l_i/(2*PI));				// 0 .. 2PI
	p.l_i_earth  -= 2*PI*floor( p.l_i_earth/(2*PI));		// 0 .. 2PI
}

	/// Inertial to Geodetic Transformation Matrix
Mat3 WGS84::T_d_i(Position p) 
{
	double lambda_d = p.lambda_d;
	double l_i = p.l_i;
	return Mat3(	-sin(lambda_d)*cos(l_i), -sin(lambda_d)*sin(l_i), cos(lambda_d),
							      -sin(l_i),		cos(l_i), 					  0,
					-cos(lambda_d)*cos(l_i), -cos(lambda_d)*sin(l_i), -sin(lambda_d) );
}

	/// Geographic to Geodetic Transformation Matrix
Mat3 WGS84::T_d_g(Position p) 
{
	double delta = p.delta;
	return Mat3( cos(delta), 0, sin(delta),
					 	  0, 1,			 0,
		        -sin(delta), 0, cos(delta) );
}

	/// Inertial to Geographic Transformation Matrix
Mat3 WGS84::T_g_i(Position p) 
{
	return T_d_g(p).inv() * T_d_i(p);
}

	/// Inertial to Body Transformation Matrix
Mat3 WGS84::T_b_i(Vec3 euler, Position p) 
{
	double phi   = euler.x;
	double theta = euler.y;
	double psi   = euler.z;

	Mat3 T_b_d(											/// Direction Cosine Matrix
		cos(psi)*cos(theta), 							sin(psi)*cos(theta)						, 				-sin(theta),
		cos(psi)*sin(theta)*sin(phi)-sin(psi)*cos(phi), sin(psi)*sin(theta)*sin(phi)+cos(psi)*cos(phi), cos(theta)*sin(phi),
		cos(psi)*sin(theta)*cos(phi)+sin(psi)*sin(phi), sin(psi)*sin(theta)*cos(phi)-cos(psi)*sin(phi), cos(theta)*cos(phi) );

	return T_b_d * T_d_i(p);
}

							// Earth to Inertial
Mat3 WGS84::T_e_i(/*Position p*/ double l)
{
//	double l = p.l_i - p.l_i_earth;
	return Mat3(  cos(l),  sin(l), 0,
				 -sin(l),  cos(l), 0,
					   0,       0, 1);
}

	/// Return Euler angles from T_b_i
Vec3 WGS84::euler(Mat3 T_b_i, Position p) 
{
	Mat3 T_b_d = T_b_i * T_d_i(p).inv();
	Vec3 e;
	e.y = asin( -T_b_d[0][2] );
	e.z = acos(  T_b_d[0][0]/cos(e.y) )*sign( T_b_d[0][1] );
	e.x = acos(  T_b_d[2][2]/cos(e.y) )*sign( T_b_d[1][2] );

	if (isnan(T_b_d[0][0]/cos(e.y)))
	{
		cout << "e.z is unreal" << endl;
		cin.get();
	}
	if (isnan(T_b_d[2][2]/cos(e.y)))
	{
		cout << "e.z is unreal" << endl;
		cin.get();
	}
	if (isinf(T_b_d[0][0]/cos(e.y)))
	{
		cout << "e.z is unreal" << endl;
		cin.get();
	}
	if (isinf(T_b_d[2][2]/cos(e.y)))
	{
		cout << "e.z is unreal" << endl;
		cin.get();
	}


	// program to limit( acos(x) ) if x exceeds bounds.
	if (T_b_d[0][0]/cos(e.y) <= -1.)
	{
		e.z = PI * sign( T_b_d[1][2] );
	}
	if (T_b_d[0][0]/cos(e.y) >= 1.)
	{
		e.z = 0.;
	}

	if (T_b_d[2][2]/cos(e.y) <= -1.)
	{
		e.z = PI * sign( T_b_d[0][1] );
	}
	if (T_b_d[2][2]/cos(e.y) >= 1.)
	{
		e.x = 0.;
	}
	return e;
}

	/// Gravity Vector
Vec3 WGS84::gravity(Vec3 xyz, Position p) 
{
	Vec3 g = Vec3( -3*sqrt(5.0)*C_2_0*pow(a/xyz.mag(),2)*sin(p.lambda_c)*cos(p.lambda_c),	
			0,
	        1 + (3/2)*sqrt(5.0)*C_2_0*pow(a/xyz.mag(),2)*(3*pow(sin(p.lambda_c),2)-1));
	
	g *= GM/pow(xyz.mag(),2);

	return g;
};

	/// Bulds the Inertial positon vector as a function of latitude, longitude and altitude.
Vec3 WGS84::InitXYZ(Position p) 
{
    p.R_0   = a * ( 1 - (f/2) * (1 - cos( 2 * p.lambda_d ) + (( 5*pow(f,2) )/16)*(1-cos(4*p.lambda_d)))); 
	p.delta = f * sin(2 * p.lambda_d) * ( 1 - (f/2) - (p.h/p.R_0));
	Mat3 T_i_g = T_d_i(p).inv() * T_d_g(p);
	return T_i_g * Vec3(0, 0, -(p.h + p.R_0));
}

	/// Geographic to Flight Path Transformation Matrix
	/// \param chi   Heading
	/// \param gamma Flight Path Angle
Mat3 WGS84::T_v_g(double chi, double gamma) 
{
	return Mat3 ( 	cos(gamma)*cos(chi), cos(gamma)*sin(chi), -sin(gamma),
							  -sin(chi),			cos(chi),			0,
					sin(gamma)*cos(chi), sin(gamma)*sin(chi),  cos(gamma) );
}
