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
			double mag = this->mag();
			if (mag == 0.0) return Vec3(0, 0, 0);	// avoid divide-by-zero → NaN
			Vec3 unit;
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
			return Mat3(0, -this->z, this->y,
    			this->z, 0, -this->x,
				-this->y, this->x, 0);
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
			// Out-of-range access: warn and return a valid reference rather than
			// falling off the end of the function (which was undefined behavior).
			cerr << "Vec3::operator[]: index " << i << " out of range [0,2]" << endl;
			return z;
		}

		/// Const array-style access (0=x, 1=y, 2=z).
		const double &Vec3::operator[]( int i) const
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
			cerr << "Vec3::operator[]: index " << i << " out of range [0,2]" << endl;
			return z;
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

		/// Tests two vectors for equality (component-wise), STL container compliance.
		bool Vec3::operator== (const Vec3& right) const {
			return this->x == right.x && this->y == right.y && this->z == right.z;
		}

		/// Tests two vectors for inequality (component-wise), STL container compliance.
		bool Vec3::operator!= (const Vec3& right) const {
			return !(*this == right);
		}

		/// Lexicographic ordering (x, then y, then z). Provides a strict weak
		/// ordering consistent with operator== so Vec3 can be a std::map/set key.
		bool Vec3::operator<  (const Vec3& right) const {
			if (x != right.x) return x < right.x;
			if (y != right.y) return y < right.y;
			return z < right.z;
		}

		/// Lexicographic ordering (mirror of operator<).
		bool Vec3::operator>  (const Vec3& right) const {
			return right < *this;
		}

		/// ostream operator for vectors.
		ostream &operator<<( ostream &stream, Vec3 vec)
		{
			stream << vec.x << " " << vec.y << " " << vec.z;
			return stream;
		}
	}
}