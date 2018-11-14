#include "MissileAero.h"
#include <cmath>
const double PI = 3.14159;

using namespace dsf::sim;
using namespace dsf::util;

Block* MissileAero::block = TClass<MissileAero,Block>::Instance()->getStatic();

	// slegers' aero from the hydra70 project has tabularized static margin
	// and leads to a slightly different formulation. Maybe capture that too ...
void MissileAero::update(double M, double rho, dsf::util::Vec3 uvw_b, dsf::util::Vec3 pqr)
{
		//	Since our sim design method has a common parent class for this class
		//	and all classes that define the above variables M, D, rho, uvw_b and pqr,
		//	we could have parent class pass references to each of these variables, and
		//	then make this a conventional update() that gets calculated in integrator
		//
	double V = uvw_b.mag();
	double v = uvw_b.y;
	double w = uvw_b.z;
	double p = pqr.x;
	double q = pqr.y;
	double r = pqr.z;

	double qS  = (PI/8)*rho*pow(V,2)*pow(D,2);
	double qSd = (PI/8)*rho*pow(V,2)*pow(D,3);

		// Normal Aero Forces
	Vec3 forces;
	forces.x = -qS*(Cx0(M) + Cx2(M)*( ( pow(v,2) + pow(w,2) ) /pow(V,2) ) );
	forces.y = -qS*(Cy0(M) + CnA(M)*(v/V));
	forces.z = -qS*(Cz0(M) + CnA(M)*(w/V));

		// Magnus Aero Forces
	Vec3 magnus;
	magnus.y =  qS*(((p*D)/(2*V))*CypA(M)*(w/V));
	magnus.z = -qS*(((p*D)/(2*V))*CypA(M)*(v/V));

		// Force contribution to Moments
	Vec3 cp, magcp;
	cp.x    = -(Cma(M)/CnA(M))*D;
	magcp.x = -(CnpA(M)/CypA(M))*D;			

		// Aero Moments
	Vec3 moments;
	moments.x = qSd*( (p*D*Clp(M))/(2*V) );
	moments.y = qSd*( (q*D*Cmq(M))/(2*V) );
	moments.z = qSd*( (r*D*Cmq(M))/(2*V) );				

	LMN = moments + cp.cross( forces ) + magcp.cross( magnus );
	XYZ = forces + magnus;
}

void MissileAero::configure(dsf::xml::xmlnode n)
{
	n.search("aero");
	filename = n.attrAsString("filename");
	D = n.attrAsDouble("area");

	cout << "using filename: " << filename << " and D " << D << endl;
	Cx0  = Table(filename,"[Cx0]");
	Cx2  = Table(filename,"[Cx2]");
	Cy0  = Table(filename,"[Cy0]");
	Cz0  = Table(filename,"[Cz0]");
	CnA  = Table(filename,"[CnA]");
	CypA = Table(filename,"[CypA]");
	Clp  = Table(filename,"[Clp]");
	Cmq  = Table(filename,"[Cmq]");
	CnpA = Table(filename,"[CnpA]");
	Cma  = Table(filename,"[Cma]");
}
