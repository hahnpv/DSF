#ifndef MAT4_H
#define MAT4_H
#include <iostream>
#include "quat.h"
class Quaternion;
namespace dsf
{
	namespace util
	{
		class Mat4
		{
		public:
			// Constructors
			Mat4() {};
			Mat4( double, double, double, double,
			  double, double, double, double,
			  double, double, double, double,
			  double, double, double, double );

			// Destructor
			~Mat4() {};

			// Accessors
			double a00, a01, a02, a03,
			   a10, a11, a12, a13,
			   a20, a21, a22, a23,
			   a30, a31, a32, a33;

			// Functions
			double det();			// determinant
			Mat4   inv();			// inverse
			Mat4 transpose();			// transpose

			// Operator Overloading
			Mat4 operator()(double, double, double, double,
					double, double, double, double,
					double, double, double, double,
					double, double, double, double);
		//    Vec3 &operator[]( int);
		//    Mat3 operator+( Mat3 m0);
		//    Mat3 operator-( Mat3 m0);
			Quaternion operator*( Quaternion q);
		//    Mat3 operator*( double c);
		//    Mat3 operator/( double c);
		 //   Mat3 operator*=( double c);
		//    Vec3 operator*( Vec3 v0);
		};
	}
}
// << operator
std::ostream &operator<<( std::ostream &stream, Mat4 mat);
#endif
