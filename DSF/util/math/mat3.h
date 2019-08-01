#pragma once

#include <iostream>
#include "vec3.h"

namespace dsf
{
	namespace util
	{

		class Mat3
		{
		public:
			// Constructors
			Mat3() {};
			Mat3( double, double, double,
			 double, double, double,
			 double, double, double );

			Mat3( Vec3, Vec3, Vec3);

			// Destructor
			~Mat3() {};

			Vec3 a0;
			Vec3 a1;
			Vec3 a2;

			// Functions
			double det();			// determinant
			Mat3   inv();			// inverse
			Mat3 transpose();			// transpose

			// Operator Overloading
			Vec3 &operator[]( int i);		// return a column vector
			Mat3 operator+( Mat3 m0);
			Mat3 operator-( Mat3 m0);
			Mat3 operator*( Mat3 m0);
			Mat3 operator*( double c);
			Mat3 operator/( double c);
			Mat3 operator*=( double c);
			Mat3 operator+=( Mat3 m);
			Vec3 operator*( Vec3 v0);

			Mat3 operator()(double a00, double a01, double a02,
							double a10, double a11, double a12,
							double a20, double a21, double a22);
		};

		// << operator
		std::ostream &operator<<( std::ostream &stream, Mat3 mat);
	}
}
