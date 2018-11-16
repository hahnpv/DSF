#include "mass.h"

using namespace dsf::sim;

Block* Mass::block = TClass<Mass,Block>::Instance()->getStatic();

Mass::Mass()
{}

void Mass::update()
{}

void Mass::configure(dsf::xml::xmlnode n)
{
	n.search("mass");

	M    = n.attrAsDouble("mass");
	area = n.attrAsDouble("area");
	I    = n.attrAsMat3("MOI");

	cout << "I: " << endl << I << endl;
	cout << "mass: " << M << " area: " << area << endl;
//	cin.get();
}
