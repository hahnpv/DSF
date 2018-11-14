#include "mat4.h"
#include "quat.h"
using namespace std;

namespace dsf
{
	namespace util
	{
		Mat4::Mat4( double a00, double a01, double a02, double a03,
				double a10, double a11, double a12, double a13,
				double a20, double a21, double a22, double a23,
				double a30, double a31, double a32, double a33)
		{
			this->a00 = a00;
			this->a01 = a01;
			this->a02 = a02;
			this->a03 = a03;
			this->a10 = a10;
			this->a11 = a11;
			this->a12 = a12;
			this->a13 = a13;
			this->a20 = a20;
			this->a21 = a21; 
			this->a22 = a22;
			this->a23 = a23;
			this->a30 = a30;
			this->a31 = a31;
			this->a32 = a32;
			this->a33 = a33;
		}

		double Mat4::det()
		{
		//    return a00*a11*a22 + a01*a12*a20 + a02*a10*a21 
		//	 - a02*a11*a20 - a01*a10*a22 - a00*a12*a21;
		}

		Mat4 Mat4::inv()
		{
		/*
			double det = this->det();
			Mat3 inv;
			inv.a00 = ( a11 * a22 - a12 * a21 ) / det;
			inv.a01 = ( a02 * a21 - a01 * a22 ) / det;
			inv.a02 = ( a01 * a12 - a11 * a02 ) / det;
			inv.a10 = ( a20 * a12 - a10 * a22 ) / det;
			inv.a11 = ( a00 * a22 - a20 * a02 ) / det;
			inv.a12 = ( a10 * a02 - a00 * a12 ) / det;
			inv.a20 = ( a10 * a21 - a20 * a11 ) / det;
			inv.a21 = ( a20 * a01 - a00 * a21 ) / det;
			inv.a22 = ( a00 * a11 - a01 * a10 ) / det;
			return inv;
		*/
		}

		Mat4 Mat4::transpose()
		{
		/*
		   Mat3 transpose;
		   transpose.a00 = a00;
		   transpose.a01 = a10;
		   transpose.a02 = a20;
		   transpose.a10 = a01;
		   transpose.a11 = a11;
		   transpose.a12 = a21;
		   transpose.a20 = a02;
		   transpose.a21 = a12;
		   transpose.a22 = a22;
		   return transpose;
		*/
		}

		Mat4 Mat4::operator()( double a00, double a01, double a02, double a03,
					   double a10, double a11, double a12, double a13,
					   double a20, double a21, double a22, double a23,
					   double a30, double a31, double a32, double a33)
		{
			this->a00 = a00;
			this->a01 = a01;
			this->a02 = a02;
			this->a03 = a03;
			this->a10 = a10;
			this->a11 = a11;
			this->a12 = a12;
			this->a13 = a13;
			this->a20 = a20;
			this->a21 = a21;
			this->a22 = a22;
			this->a23 = a23;
			this->a30 = a30;
			this->a31 = a31;
			this->a32 = a32;
			this->a33 = a33;
			return *this;
		}
		/*
		// BROKE -- DO NOT USE
		Vec3 &Mat3::operator[]( int i)
		{
			switch( i)
			{
			case 0:
			{
				Vec3 x(a00, a11, a22);
				return (Vec3 &)Vec3(a00, a01, a02);			
			}
			case 1:
			{
				Vec3 x(a10, a11, a12);
				return x;
			}
			case 2:
			{
				Vec3 x(a20, a21, a22);
				return x;
			}
			}
		}






		Mat3 Mat3::operator+(Mat3 m0)
		{
			Mat3 m1;
			m1.a00 = this->a00 + m0.a00;
			m1.a01 = this->a01 + m0.a01;
			m1.a02 = this->a02 + m0.a02;
			m1.a10 = this->a10 + m0.a10;
			m1.a11 = this->a11 + m0.a11;
			m1.a12 = this->a12 + m0.a12;
			m1.a20 = this->a20 + m0.a20;
			m1.a21 = this->a21 + m0.a21;
			m1.a22 = this->a22 + m0.a22;
			return m1;
		}

		Mat3 Mat3::operator-(Mat3 m0)
		{
			Mat3 m1;
			m1.a00 = this->a00 - m0.a00;
			m1.a01 = this->a01 - m0.a01;
			m1.a02 = this->a02 - m0.a02;
			m1.a10 = this->a10 - m0.a10;
			m1.a11 = this->a11 - m0.a11;
			m1.a12 = this->a12 - m0.a12;
			m1.a20 = this->a20 - m0.a20;
			m1.a21 = this->a21 - m0.a21;
			m1.a22 = this->a22 - m0.a22;
			return m1;
		}
		*/
		Quaternion Mat4::operator*( Quaternion q0)
		{
			Quaternion q1;
			q1.x = this->a00 * q0.x + this->a01 * q0.y + this->a02 * q0.z + this->a03 * q0.w;
			q1.y = this->a10 * q0.x + this->a11 * q0.y + this->a12 * q0.z + this->a13 * q0.w;
			q1.z = this->a20 * q0.x + this->a21 * q0.y + this->a22 * q0.z + this->a23 * q0.w;
			q1.w = this->a30 * q0.x + this->a31 * q0.y + this->a32 * q0.z + this->a33 * q0.w;
			return q1;

		}
		/*
		Mat3 Mat3::operator*(double c)
		{
			Mat3 m1;
			m1.a00 = this->a00 * c;
			m1.a01 = this->a01 * c;
			m1.a02 = this->a02 * c;
			m1.a10 = this->a10 * c;
			m1.a11 = this->a11 * c;
			m1.a12 = this->a12 * c;
			m1.a20 = this->a20 * c;
			m1.a21 = this->a21 * c;
			m1.a22 = this->a22 * c;
			return m1;
		}

		Mat3 Mat3::operator/(double c)
		{
			Mat3 m1;
			m1.a00 = this->a00 / c;
			m1.a01 = this->a01 / c;
			m1.a02 = this->a02 / c;
			m1.a10 = this->a10 / c;
			m1.a11 = this->a11 / c;
			m1.a12 = this->a12 / c;
			m1.a20 = this->a20 / c;
			m1.a21 = this->a21 / c;
			m1.a22 = this->a22 * c;
			return m1;
		}

		Mat3 Mat3::operator*=( double c)
		{
			this->a00 *= c;
			this->a01 *= c;
			this->a02 *= c;
			this->a10 *= c;
			this->a11 *= c;
			this->a12 *= c;
			this->a20 *= c;
			this->a21 *= c;
			this->a22 *= c;
			return *this;
		}

		Vec3 Mat3::operator*(Vec3 v0)
		{
			Vec3 v1;
			v1.x = this->a00 * v0.x + this->a01 * v0.y + this->a02 * v0.z;
			v1.y = this->a10 * v0.x + this->a11 * v0.y + this->a12 * v0.z;
			v1.z = this->a20 * v0.x + this->a21 * v0.y + this->a22 * v0.z;
			return v1;
		}
		*/
		ostream &operator<<(ostream &stream, Mat4 mat)
		{
			stream << mat.a00 << " " << mat.a01 << " " << mat.a02 << " " << mat.a03 << endl
			   << mat.a10 << " " << mat.a11 << " " << mat.a12 << " " << mat.a13 << endl
			   << mat.a20 << " " << mat.a21 << " " << mat.a22 << " " << mat.a23 << endl
			   << mat.a30 << " " << mat.a31 << " " << mat.a32 << " " << mat.a33 << endl;
			return stream;
		}
	}
}