#pragma once 

#include "sim/block.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"

	/// struct for holding WGS84 positional data
struct Position
{
	double l_i;				/// longitude wrt inertial
	double l_i_earth;		/// longitude wrt geodetic
	double R_0;				/// radius of the earth
	double h;				/// altitude above earth
	double lambda_d;		/// latitude, geodetic
	double lambda_c;		/// latitude, spherical earth
	double delta;			/// offset between lambda_d and lambda_c for TM.
};

class WGS84 : public dsf::sim::Block
{
public:
	WGS84(void);

	static Block *block;

	void calculate(dsf::util::Vec3 xyz, double t, Position &p);		///< calculates l_i, lambda_d, h, given xyz Vector in inertial coordinates
	dsf::util::Vec3 gravity(dsf::util::Vec3 xyz, Position p);		///< Returns Gravity vector

	dsf::util::Mat3 T_g_i(Position p);							///< Inertial to Geographic TM
	dsf::util::Mat3 T_d_i(Position p);							///< Inertial to Geodetic TM
	dsf::util::Mat3 T_b_i(dsf::util::Vec3 euler, Position p);	///< Inertial to Body TM
	dsf::util::Mat3 T_d_g(Position p);							///< Geographic to Geodetic TM
	dsf::util::Mat3 T_e_i(double);								///< Inertial to Earth TM
	dsf::util::Mat3 T_v_g(double chi, double gamma);			///< Geographic to Velocity TM

	dsf::util::Vec3 euler(dsf::util::Mat3 T_b_i, Position p);	///< Calculate Euler angles from T_b_i
	dsf::util::Vec3 InitXYZ(Position p);						///< Initialize XYZ from lat/lon/alt

	dsf::util::Vec3 w_e_i;
protected:
	double w_earth;					/// rot rate of earth, sidereal
	double a, f;					/// WGS84 parameters
	double GM, C_2_0;				/// Gravitational Parameters
};

