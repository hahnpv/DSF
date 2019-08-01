#pragma once
#include <iostream>

namespace dsf
{
	namespace util
	{

				// 3D Vector class
		class Mat3;
		class Vec3
		{
		public:
			// Constructors
			Vec3() { x=0; y=0; z=0;};
			Vec3(double, double, double);

			// Destructor
			~Vec3() {};

			// Accessors
			double x, y, z;			// member elements are public

			// Functions
			double mag();				// magnitude
			Vec3   unit();				// unit vector
			Vec3   cross(Vec3 vec);		// cross product
			Mat3   skew();				// skew-symmetric form of the vector
			double dot(Vec3 dot);		// dot product
			Vec3 scale( double a);		// scale a vector

			// Operator Overloading
			double &operator[](int i);	// array accessor
			Vec3 operator+(Vec3 vec);
			Vec3 operator*( double c);
			Vec3 operator/( double c);
			Vec3 operator*=( double c);
			Vec3 operator+=( Vec3 vec);
			Vec3 operator-=( Vec3 vec);
			Vec3 operator-( Vec3 vec);
			Vec3 operator()(double x, double y, double z);

			// STL Compliance
			bool operator== (const Vec3& right) const;
			bool operator!= (const Vec3& right) const;
			bool operator<  (const Vec3& right) const;
			bool operator>  (const Vec3& right) const;
		};

		// << operator
		std::ostream &operator<<( std::ostream &stream, Vec3 vec);
	}
}
