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

		// The determinant and inverse use the six 2x2 minors from the top two
		// rows (s0..s5) and the bottom two rows (c0..c5) — the standard cofactor
		// expansion for a 4x4 matrix.
		double Mat4::det()
		{
			double s0 = a00*a11 - a10*a01;
			double s1 = a00*a12 - a10*a02;
			double s2 = a00*a13 - a10*a03;
			double s3 = a01*a12 - a11*a02;
			double s4 = a01*a13 - a11*a03;
			double s5 = a02*a13 - a12*a03;

			double c5 = a22*a33 - a32*a23;
			double c4 = a21*a33 - a31*a23;
			double c3 = a21*a32 - a31*a22;
			double c2 = a20*a33 - a30*a23;
			double c1 = a20*a32 - a30*a22;
			double c0 = a20*a31 - a30*a21;

			return s0*c5 - s1*c4 + s2*c3 + s3*c2 - s4*c1 + s5*c0;
		}

		Mat4 Mat4::inv()
		{
			double s0 = a00*a11 - a10*a01;
			double s1 = a00*a12 - a10*a02;
			double s2 = a00*a13 - a10*a03;
			double s3 = a01*a12 - a11*a02;
			double s4 = a01*a13 - a11*a03;
			double s5 = a02*a13 - a12*a03;

			double c5 = a22*a33 - a32*a23;
			double c4 = a21*a33 - a31*a23;
			double c3 = a21*a32 - a31*a22;
			double c2 = a20*a33 - a30*a23;
			double c1 = a20*a32 - a30*a22;
			double c0 = a20*a31 - a30*a21;

			double det = s0*c5 - s1*c4 + s2*c3 + s3*c2 - s4*c1 + s5*c0;
			if (det == 0.0)
			{
				cerr << "Mat4::inv: singular matrix (det == 0)" << endl;
				return Mat4();		// zero matrix
			}
			double invdet = 1.0 / det;

			Mat4 b;
			b.a00 = ( a11*c5 - a12*c4 + a13*c3) * invdet;
			b.a01 = (-a01*c5 + a02*c4 - a03*c3) * invdet;
			b.a02 = ( a31*s5 - a32*s4 + a33*s3) * invdet;
			b.a03 = (-a21*s5 + a22*s4 - a23*s3) * invdet;

			b.a10 = (-a10*c5 + a12*c2 - a13*c1) * invdet;
			b.a11 = ( a00*c5 - a02*c2 + a03*c1) * invdet;
			b.a12 = (-a30*s5 + a32*s2 - a33*s1) * invdet;
			b.a13 = ( a20*s5 - a22*s2 + a23*s1) * invdet;

			b.a20 = ( a10*c4 - a11*c2 + a13*c0) * invdet;
			b.a21 = (-a00*c4 + a01*c2 - a03*c0) * invdet;
			b.a22 = ( a30*s4 - a31*s2 + a33*s0) * invdet;
			b.a23 = (-a20*s4 + a21*s2 - a23*s0) * invdet;

			b.a30 = (-a10*c3 + a11*c1 - a12*c0) * invdet;
			b.a31 = ( a00*c3 - a01*c1 + a02*c0) * invdet;
			b.a32 = (-a30*s3 + a31*s1 - a32*s0) * invdet;
			b.a33 = ( a20*s3 - a21*s1 + a22*s0) * invdet;
			return b;
		}

		Mat4 Mat4::transpose()
		{
			Mat4 t;
			t.a00 = a00; t.a01 = a10; t.a02 = a20; t.a03 = a30;
			t.a10 = a01; t.a11 = a11; t.a12 = a21; t.a13 = a31;
			t.a20 = a02; t.a21 = a12; t.a22 = a22; t.a23 = a32;
			t.a30 = a03; t.a31 = a13; t.a32 = a23; t.a33 = a33;
			return t;
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
		Quaternion Mat4::operator*( Quaternion q0_in)
		{
			Quaternion q1;
			q1.q0 = this->a00 * q0_in.q0 + this->a01 * q0_in.q1 + this->a02 * q0_in.q2 + this->a03 * q0_in.q3;
			q1.q1 = this->a10 * q0_in.q0 + this->a11 * q0_in.q1 + this->a12 * q0_in.q2 + this->a13 * q0_in.q3;
			q1.q2 = this->a20 * q0_in.q0 + this->a21 * q0_in.q1 + this->a22 * q0_in.q2 + this->a23 * q0_in.q3;
			q1.q3 = this->a30 * q0_in.q0 + this->a31 * q0_in.q1 + this->a32 * q0_in.q2 + this->a33 * q0_in.q3;
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