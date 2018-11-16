#include "ReentryAero.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* ReentryAero::block = TClass<ReentryAero,Block>::Instance()->getStatic();

void ReentryAero::configure(dsf::xml::xmlnode n)
{
	CdS = n.attrAsDouble("CdS");
	cout << "CdS: " << CdS << endl;
//	cin.get();
}

void ReentryAero::update(double M, double rho, dsf::util::Vec3 uvw_b, dsf::util::Vec3 pqr)
{
	// simple; make a function of ballistic coefficient and input via xml
//	double drag = 0.5 * rho * pow(uvw_b.mag(), 2) * CdS;
//	Vec3 direction = uvw_b.unit();
//	XYZ = direction * -drag;

	/// Simple 1D drag model (opposing incoming flow)
	XYZ = uvw_b * (-0.5 * rho * uvw_b.mag() * CdS);
}
