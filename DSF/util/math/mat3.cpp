#include "mat3.h"

using namespace std;

namespace dsf
{
	namespace util
	{
		/// Assignment constructor.
		Mat3::Mat3( double a00, double a01, double a02, 
				double a10, double a11, double a12, 
				double a20, double a21, double a22)
		{
			a0[0] = a00;
			a0[1] = a01;
			a0[2] = a02;

			a1[0] = a10;
			a1[1] = a11;
			a1[2] = a12;

			a2[0] = a20;
			a2[1] = a21;
			a2[2] = a22;
		}

		Mat3::Mat3( Vec3 v0, Vec3 v1, Vec3 v2)
		{
			a0 = v0;
			a1 = v1;
			a2 = v2;
		}


		/// Calculates the determinant of the matrix.
		double Mat3::det()
		{
			return a0[0]*a1[1]*a2[2] + a0[1]*a1[2]*a2[0] + a0[2]*a1[0]*a2[1] 
				 - a0[2]*a1[1]*a2[0] - a0[1]*a1[0]*a2[2] - a0[0]*a1[2]*a2[1];
		}

		/// Calculates the inverse of the matrix.
		Mat3 Mat3::inv()
		{
			double invdet = 1/this->det();

			Mat3 inv;

			inv.a0[0] = ( a1[1] * a2[2] - a1[2] * a2[1] ) * invdet;
			inv.a0[1] = ( a0[2] * a2[1] - a0[1] * a2[2] ) * invdet;
			inv.a0[2] = ( a0[1] * a1[2] - a1[1] * a0[2] ) * invdet;
			inv.a1[0] = ( a2[0] * a1[2] - a1[0] * a2[2] ) * invdet;
			inv.a1[1] = ( a0[0] * a2[2] - a2[0] * a0[2] ) * invdet;
			inv.a1[2] = ( a1[0] * a0[2] - a0[0] * a1[2] ) * invdet;
			inv.a2[0] = ( a1[0] * a2[1] - a2[0] * a1[1] ) * invdet;
			inv.a2[1] = ( a2[0] * a0[1] - a0[0] * a2[1] ) * invdet;
			inv.a2[2] = ( a0[0] * a1[1] - a0[1] * a1[0] ) * invdet;

			return inv;
		}

		/// Calculates the transpose of the matrix.
		/// If the matrix is a tensor, transpose = determinant, \n
		/// and the transpose is less computationally intense.
		Mat3 Mat3::transpose()
		{
		   Mat3 transpose;

		   transpose.a0[0] = a0[0];
		   transpose.a0[1] = a1[0];
		   transpose.a0[2] = a2[0];
		   transpose.a1[0] = a0[1];
		   transpose.a1[1] = a1[1];
		   transpose.a1[2] = a2[1];
		   transpose.a2[0] = a0[2];
		   transpose.a2[1] = a1[2];
		   transpose.a2[2] = a2[2];

		   return transpose;
		}

		/// [] operator.
		/// Returns a Vec3, whose operator[] provides the second bracket accessor.
		Vec3 &Mat3::operator[](int i)
		{
			Vec3 v0;
			
			if ( i == 0)
			{
				return a0;
			}
			else if ( i == 1)
			{
				return a1;
			}
			else if ( i == 2)
			{
				return a2;
			}
		}

		/// Addition operator with another matrix.
		Mat3 Mat3::operator+(Mat3 m0)
		{
			Mat3 m1;
			m1.a0[0] = this->a0[0] + m0.a0[0];
			m1.a0[1] = this->a0[1] + m0.a0[1];
			m1.a0[2] = this->a0[2] + m0.a0[2];
			m1.a1[0] = this->a1[0] + m0.a1[0];
			m1.a1[1] = this->a1[1] + m0.a1[1];
			m1.a1[2] = this->a1[2] + m0.a1[2];
			m1.a2[0] = this->a2[0] + m0.a2[0];
			m1.a2[1] = this->a2[1] + m0.a2[1];
			m1.a2[2] = this->a2[2] + m0.a2[2];
			return m1;
		}

		/// Subtraction operator with another matrix.
		Mat3 Mat3::operator-(Mat3 m0)
		{
			Mat3 m1;
			m1.a0[0] = this->a0[0] - m0.a0[0];
			m1.a0[1] = this->a0[1] - m0.a0[1];
			m1.a0[2] = this->a0[2] - m0.a0[2];
			m1.a1[0] = this->a1[0] - m0.a1[0];
			m1.a1[1] = this->a1[1] - m0.a1[1];
			m1.a1[2] = this->a1[2] - m0.a1[2];
			m1.a2[0] = this->a2[0] - m0.a2[0];
			m1.a2[1] = this->a2[1] - m0.a2[1];
			m1.a2[2] = this->a2[2] - m0.a2[2];
			return m1;
		}

		/// Multiplication operator with another matrix.
		Mat3 Mat3::operator*( Mat3 m2)
		{
		  Mat3 m;
		  Mat3 m1 = *this;
			m.a0[0] = m1[0][0] * m2[0][0] + m1[0][1] * m2[1][0] + m1[0][2] * m2[2][0];
			m.a0[1] = m1[0][0] * m2[0][1] + m1[0][1] * m2[1][1] + m1[0][2] * m2[2][1];
			m.a0[2] = m1[0][0] * m2[0][2] + m1[0][1] * m2[1][2] + m1[0][2] * m2[2][2];
			m.a1[0] = m1[1][0] * m2[0][0] + m1[1][1] * m2[1][0] + m1[1][2] * m2[2][0];
			m.a1[1] = m1[1][0] * m2[0][1] + m1[1][1] * m2[1][1] + m1[1][2] * m2[2][1];
			m.a1[2] = m1[1][0] * m2[0][2] + m1[1][1] * m2[1][2] + m1[1][2] * m2[2][2];
			m.a2[0] = m1[2][0] * m2[0][0] + m1[2][1] * m2[1][0] + m1[2][2] * m2[2][0];
			m.a2[1] = m1[2][0] * m2[0][1] + m1[2][1] * m2[1][1] + m1[2][2] * m2[2][1];
			m.a2[2] = m1[2][0] * m2[0][2] + m1[2][1] * m2[1][2] + m1[2][2] * m2[2][2];
		  return m;
		}

		/// Multiplication operator with a scalar.
		Mat3 Mat3::operator*(double c)
		{
			Mat3 m1;
			m1.a0[0] = this->a0[0] * c;
			m1.a0[1] = this->a0[1] * c;
			m1.a0[2] = this->a0[2] * c;
			m1.a1[0] = this->a1[0] * c;
			m1.a1[1] = this->a1[1] * c;
			m1.a1[2] = this->a1[2] * c;
			m1.a2[0] = this->a2[0] * c;
			m1.a2[1] = this->a2[1] * c;
			m1.a2[2] = this->a2[2] * c;
			return m1;
		}

		/// Division operator with a scalar.
		Mat3 Mat3::operator/(double c)
		{
			Mat3 m1;
			m1.a0[0] = this->a0[0] / c;
			m1.a0[1] = this->a0[1] / c;
			m1.a0[2] = this->a0[2] / c;
			m1.a1[0] = this->a1[0] / c;
			m1.a1[1] = this->a1[1] / c;
			m1.a1[2] = this->a1[2] / c;
			m1.a2[0] = this->a2[0] / c;
			m1.a2[1] = this->a2[1] / c;
			m1.a2[2] = this->a2[2] / c;
			return m1;
		}

		/// Multiplicative operator with a scalar.
		Mat3 Mat3::operator*=( double c)
		{
			this->a0[0] *= c;
			this->a0[1] *= c;
			this->a0[2] *= c;
			this->a1[0] *= c;
			this->a1[1] *= c;
			this->a1[2] *= c;
			this->a2[0] *= c;
			this->a2[1] *= c;
			this->a2[2] *= c;
			return *this;
		}

		/// Additive operator with a Matrix.
		Mat3 Mat3::operator+=( Mat3 m)
		{
			this->a0[0] += m.a0[0];
			this->a0[1] += m.a0[1];
			this->a0[2] += m.a0[2];
			this->a1[0] += m.a1[0];
			this->a1[1] += m.a1[1];
			this->a1[2] += m.a1[2];
			this->a2[0] += m.a2[0];
			this->a2[1] += m.a2[1];
			this->a2[2] += m.a2[2];
			return *this;
		}

		/// Multiplication with a Vec3.
		Vec3 Mat3::operator*(Vec3 v0)
		{
			Vec3 v1;
			v1.x = this->a0[0] * v0.x + this->a0[1] * v0.y + this->a0[2] * v0.z;
			v1.y = this->a1[0] * v0.x + this->a1[1] * v0.y + this->a1[2] * v0.z;
			v1.z = this->a2[0] * v0.x + this->a2[1] * v0.y + this->a2[2] * v0.z;
			return v1;
		}

		/// Overloaded () operator, allows for setting of all 9 matrix values.
		Mat3 Mat3::operator()(double a00, double a01, double a02,
							  double a10, double a11, double a12,
							  double a20, double a21, double a22)
		{
			this->a0[0] = a00;
			this->a0[1] = a01;
			this->a0[2] = a02;

			this->a1[0] = a10;
			this->a1[1] = a11;
			this->a1[2] = a12;

			this->a2[0] = a20;
			this->a2[1] = a21;
			this->a2[2] = a22;

			return *this;
		}

		/// ostream operator for stream printing.
		ostream &operator<<(ostream &stream, Mat3 mat)
		{
			stream << mat.a0[0] << " " << mat.a0[1] << " " << mat.a0[2] << endl
			   << mat.a1[0] << " " << mat.a1[1] << " " << mat.a1[2] << endl
			   << mat.a2[0] << " " << mat.a2[1] << " " << mat.a2[2] << endl;
			return stream;
		}
	}
}
