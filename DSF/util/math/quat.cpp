#include "quat.h"
#include "mat3.h"
#include <cmath>
using namespace std;

namespace dsf
{
	namespace util
	{
		Quaternion::Quaternion(double phi, double theta, double psi)
		{
			// 3-2-1 (ZYX) Euler sequence to quaternion
			double cp = cos(phi/2),   sp = sin(phi/2);
			double ct = cos(theta/2), st = sin(theta/2);
			double cs = cos(psi/2),   ss = sin(psi/2);

			q0 = cp*ct*cs + sp*st*ss;   // scalar
			q1 = sp*ct*cs - cp*st*ss;   // vector-x
			q2 = cp*st*cs + sp*ct*ss;   // vector-y
			q3 = cp*ct*ss - sp*st*cs;   // vector-z
		}

		Quaternion::Quaternion(double q0, double q1, double q2, double q3)
			: q0(q0), q1(q1), q2(q2), q3(q3)
		{
		}

		Mat3 Quaternion::dcm() const
		{
			// Quaternion to body-to-inertial DCM
			// Equivalent to the rotation matrix C(q)
			Mat3 C;
			C.a0.x = q0*q0 + q1*q1 - q2*q2 - q3*q3;
			C.a0.y = 2*(q1*q2 + q0*q3);
			C.a0.z = 2*(q1*q3 - q0*q2);

			C.a1.x = 2*(q1*q2 - q0*q3);
			C.a1.y = q0*q0 - q1*q1 + q2*q2 - q3*q3;
			C.a1.z = 2*(q2*q3 + q0*q1);

			C.a2.x = 2*(q1*q3 + q0*q2);
			C.a2.y = 2*(q2*q3 - q0*q1);
			C.a2.z = q0*q0 - q1*q1 - q2*q2 + q3*q3;
			return C;
		}

		void Quaternion::normalize()
		{
			double mag = magnitude();
			if (mag > 0) {
				q0 /= mag;
				q1 /= mag;
				q2 /= mag;
				q3 /= mag;
			}
		}

		Quaternion Quaternion::quat_mult(const Quaternion& r) const
		{
			// Hamilton product: this ⊗ r
			// [s1,v1] ⊗ [s2,v2] = [s1*s2 - v1·v2,  s1*v2 + s2*v1 + v1×v2]
			return Quaternion(
				q0*r.q0 - q1*r.q1 - q2*r.q2 - q3*r.q3,   // scalar
				q0*r.q1 + q1*r.q0 + q2*r.q3 - q3*r.q2,   // vector-x
				q0*r.q2 - q1*r.q3 + q2*r.q0 + q3*r.q1,   // vector-y
				q0*r.q3 + q1*r.q2 - q2*r.q1 + q3*r.q0    // vector-z
			);
		}

		double Quaternion::phi() const
		{
			// Roll: atan2(2(q0*q1 + q2*q3), 1 - 2(q1² + q2²))
			return atan2(2*(q0*q1 + q2*q3), 1 - 2*(q1*q1 + q2*q2));
		}

		double Quaternion::theta() const
		{
			// Pitch: asin(2(q0*q2 - q3*q1)), clamped to avoid NaN
			double sinp = 2*(q0*q2 - q3*q1);
			if (sinp >= 1.0) return M_PI/2;
			if (sinp <= -1.0) return -M_PI/2;
			return asin(sinp);
		}

		double Quaternion::psi() const
		{
			// Yaw: atan2(2(q0*q3 + q1*q2), 1 - 2(q2² + q3²))
			return atan2(2*(q0*q3 + q1*q2), 1 - 2*(q2*q2 + q3*q3));
		}

		Quaternion Quaternion::operator*(double c) const
		{
			return Quaternion(q0*c, q1*c, q2*c, q3*c);
		}

		Quaternion Quaternion::operator+(const Quaternion& rhs) const
		{
			return Quaternion(q0 + rhs.q0, q1 + rhs.q1, q2 + rhs.q2, q3 + rhs.q3);
		}

		Quaternion& Quaternion::operator+=(const Quaternion& rhs)
		{
			q0 += rhs.q0;
			q1 += rhs.q1;
			q2 += rhs.q2;
			q3 += rhs.q3;
			return *this;
		}

		Quaternion Quaternion::operator()(double phi, double theta, double psi)
		{
			double cp = cos(phi/2),   sp = sin(phi/2);
			double ct = cos(theta/2), st = sin(theta/2);
			double cs = cos(psi/2),   ss = sin(psi/2);

			q0 = cp*ct*cs + sp*st*ss;
			q1 = sp*ct*cs - cp*st*ss;
			q2 = cp*st*cs + sp*ct*ss;
			q3 = cp*ct*ss - sp*st*cs;
			return *this;
		}

		ostream &operator<<(ostream &stream, Quaternion quat)
		{
			stream << quat.q0 << " " << quat.q1 << " " << quat.q2 << " " << quat.q3;
			return stream;
		}
	}
}