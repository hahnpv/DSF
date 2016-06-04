#include "vec3.h"
#include "mat3.h"
#include <cmath>
using namespace std;

namespace dsf
{
	namespace util
	{
		Vec3::Vec3(double x, double y, double z)
		{
			this->x = x;
			this->y = y;
			this->z = z;
		}

		/// Return the magnitude of the vector.
		double Vec3::mag()
		{
			return sqrt( x*x + y*y + z*z );
		}

		/// Return a unit vector, |v|.
		Vec3 Vec3::unit()
		{
			Vec3 unit;
			double mag = this->mag();
			unit.x = this->x / mag;
			unit.y = this->y / mag;
			unit.z = this->z / mag;
			return unit;
		}

		/// Return the cross product of two vectors.
		Vec3 Vec3::cross(Vec3 vec)
		{
			Vec3 crossProduct;
			crossProduct.x =   this->y*vec.z - this->z*vec.y;
			crossProduct.y = -(this->x*vec.z - this->z*vec.x);
			crossProduct.z =   this->x*vec.y - this->y*vec.x;
			return crossProduct; 
		}

		/// Return the skew-symmetric form of the vector (an off-diagonal matrix).
		Mat3 Vec3::skew()
		{
			return Mat3(0, this->z, -this->y,
    			-this->z, 0, this->x,
				 this->y, -this->x, 0);
		}

		/// Dot product of two vectors.
		double Vec3::dot(Vec3 dot)
		{
			return x*dot.x + y*dot.y + z*dot.z;
		}

		/// [] operator allows access to individal members of the vector.
		double &Vec3::operator[]( int i)
		{
			switch( i)
			{
			case 0:
				return x;
			case 1:
				return y;
			case 2:
				return z;
			}
		}

		/// Addition operator with another vector.
		Vec3 Vec3::operator+( Vec3 v0)
		{
			Vec3 v1;
			v1.x = this->x + v0.x;
			v1.y = this->y + v0.y;
			v1.z = this->z + v0.z;
			return v1;
		}

		/// Subtraction with a vector.
		Vec3 Vec3::operator-( Vec3 v0)
		{
			Vec3 v1;
			v1.x = this->x - v0.x;
			v1.y = this->y - v0.y;
			v1.z = this->z - v0.z;
			return v1;
		}

		/// Multiplication operator with a scalar.
		Vec3 Vec3::operator*(double c)
		{
			Vec3 v1;
			v1.x = this->x * c;
			v1.y = this->y * c;
			v1.z = this->z * c;
			return v1;
		}

		/// Division oeprator with a scalar.
		Vec3 Vec3::operator/(double c)
		{
			Vec3 v1;
			v1.x = this->x / c;
			v1.y = this->y / c;
			v1.z = this->z / c;
			return v1;
		}

		/// Multiplicative operator with a scalar.
		Vec3 Vec3::operator*=( double c)
		{
			this->x *= c;
			this->y *= c;
			this->z *= c;
			return *this;
		}

		/// Additive operator with a vector.
		Vec3 Vec3::operator+=( Vec3 vec )
		{
			this->x += vec.x;
			this->y += vec.y;
			this->z += vec.z;
			return *this;
		}

		/// Subtractive operator with a vector.
		Vec3 Vec3::operator-=( Vec3 vec)
		{
			this->x -= vec.x;
			this->y -= vec.y;
			this->z -= vec.z;
			return *this;
		}

		/// () operator allows setting of all three vector members at once.
		Vec3 Vec3::operator()(double x, double y, double z)
		{
			this->x = x;
			this->y = y;
			this->z = z;
			return *this;
		}

		/// Tests two vectors for equality, STL container compliance.
		bool Vec3::operator== (const Vec3& right) const {

			if ( sqrt( this->x*this->x + this->y*this->y + this->z*this->z ) == sqrt( right.x*right.x + right.y*right.y + right.z*right.z ))
				return true;
			else
				return false;
		}

		/// Tests two vectors for inequality, STL container compliance.
		bool Vec3::operator!= (const Vec3& right) const {

			if ( sqrt( this->x*this->x + this->y*this->y + this->z*this->z ) != sqrt( right.x*right.x + right.y*right.y + right.z*right.z ))
				return true;
			else
				return false;
		}

		/// Tests the relative magnitude of two vectors, STL container compliance.
		bool Vec3::operator<  (const Vec3& right) const {

			// defining < by magnitude
			if ( sqrt( this->x*this->x + this->y*this->y + this->z*this->z ) < sqrt( right.x*right.x + right.y*right.y + right.z*right.z ))
				return true;
			else
				return false;
		}

		/// Tests the relative magnitude of two vectors, STL container compliance.
		bool Vec3::operator>  (const Vec3& right) const {

			// defining > by magnitude
			if ( sqrt( this->x*this->x + this->y*this->y + this->z*this->z ) > sqrt( right.x*right.x + right.y*right.y + right.z*right.z ))
				return true;
			else
				return false;
		}

		/// ostream operator for vectors.
		ostream &operator<<( ostream &stream, Vec3 vec)
		{
			stream << vec.x << " " << vec.y << " " << vec.z;
			return stream;
		}
	}
}