#ifndef QUAT_H
#define QUAT_H
#include <iostream>

class Mat3;
class Mat4;
namespace dsf
{
	namespace util
	{

		class Quaternion
		{
		public:
			// Constructors
			Quaternion() {};
			Quaternion(double, double, double);		// from euler
			Quaternion(double, double, double, double);	// from x y z w


			// Destructor
			~Quaternion() {};

			// Accessors
			inline double phi() { return 1.0;};
			inline double theta() { return 1.0;};
			inline double psi() { return 1.0;};
			Mat3 Teb();					// earth transformation matrix

			// Functions
			void normalize();

			// Operator Overloading
		 //   Quaternion operator*( Mat4 m);		// matrix multiplication
			Quaternion operator*( double c);		// scale
			Quaternion operator()(double phi, double theta, double psi);	// set via euler angles
								// quat mult, add, etc

			// Quaternion Elements
			double x, y, z, w;
		};
		std::ostream &operator<<(std::ostream &stream, Quaternion quat);
	}
}
#endif
