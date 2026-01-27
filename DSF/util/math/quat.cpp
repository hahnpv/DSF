#include "quat.h"
#include "mat3.h"
#include "mat4.h"
#include <cmath>
using namespace std;

namespace dsf
{
	namespace util
	{
		Quaternion::Quaternion(double phi, double theta, double psi)
		{
			x = cos(psi/2)*cos(theta/2)*cos(phi/2) + sin(psi/2)*sin(theta/2)*sin(phi/2);
			y = cos(psi/2)*cos(theta/2)*sin(phi/2) - sin(psi/2)*sin(theta/2)*cos(phi/2);
			z = cos(psi/2)*sin(theta/2)*cos(phi/2) + sin(psi/2)*cos(theta/2)*sin(phi/2);
			w = sin(psi/2)*cos(theta/2)*cos(phi/2) - cos(psi/2)*sin(theta/2)*sin(phi/2);
		}

		Quaternion::Quaternion(double x, double y, double z, double w)
		{
			this->x = x;
			this->y = y;
			this->z = z;
			this->w = w;
		}

		Mat3 Quaternion::Teb()
		{
			Mat3 Teb;
			Teb.a0.x = x*x + y*y -z*z - w*w;
			Teb.a1.x = 2*(y*z - x*w);
			Teb.a2.x = 2*(y*w + x*z);
			Teb.a0.y = 2*(y*z + x*w);
			Teb.a1.y = x*x - y*y + z*z - w*w;
			Teb.a2.y = 2*(z*w - x*y);
			Teb.a0.z = 2*(y*w - x*z);
			Teb.a1.z = 2*(z*w + x*y);
			Teb.a2.z = x*x - y*y - z*z + w*w;
			return Teb;
		} 

		void Quaternion::normalize()
		{
			double magnitude = sqrt( x*x + y*y + z*z + w*w );
			if(magnitude > 0) {
				x /= magnitude;
				y /= magnitude;
				z /= magnitude;
				w /= magnitude;
			}
		}

		Quaternion Quaternion::operator*( double c)
		{
			Quaternion q;
			q.x = this->x * c;
			q.y = this->y * c;
			q.z = this->z * c;
			q.w = this->w * c;
			return q;
		}

		Quaternion Quaternion::operator()( double phi, double theta, double psi)
		{
			x = cos(psi/2)*cos(theta/2)*cos(phi/2) + sin(psi/2)*sin(theta/2)*sin(phi/2);
			y = cos(psi/2)*cos(theta/2)*sin(phi/2) - sin(psi/2)*sin(theta/2)*cos(phi/2);
			z = cos(psi/2)*sin(theta/2)*cos(phi/2) + sin(psi/2)*cos(theta/2)*sin(phi/2);
			w = sin(psi/2)*cos(theta/2)*cos(phi/2) - cos(psi/2)*sin(theta/2)*sin(phi/2);
			return *this;
		}


		ostream &operator<<(ostream &stream, Quaternion quat)
		{
			stream << quat.x << " " << quat.y << " " << quat.z << " " << quat.w;
			return stream;
		}
	}
}