#include "vehicle.h"

#include "sim/TRefDict.h"
#include "sim/TClassDict.h"

dsf::sim::Block* Vehicle::block = dsf::sim::TClass<Vehicle,Block>::Instance()->getStatic();

void Vehicle::configure(dsf::xml::xmlnode n)
{
	int ix = n.numchild();
	for (int i = 0; i < ix; i++)
	{
		n.child(i);
		std::string model = n.attrAsString("id");
		std::string label = n.attrAsString("name");
		addChild( dsf::sim::TRefUnique<Block>( model));
		n.parent();
	}

	for (int i = 0; i < ix; i++)
	{
		n.child( i);
		children[i]->configure( n);
		n.parent();
	}

	for(int i = 0; i < ix; i++)
	{
		ForceAndMoment * f = dynamic_cast<ForceAndMoment*>( children[i]);
		if ( f != 0)
		{
			cout << "found a ForceAndMoment interface: " << typeid(f).name() << endl;
			force_moment.push_back( f);
		}
	}
	for(int i = 0; i < ix; i++)
	{
		MassInterface * m = dynamic_cast<MassInterface*>( children[i]);
		if ( m != 0)
		{
			cout << "found a mass interface: " << typeid(m).name() << endl;
			mass_interface.push_back( m);
		}
	}
}
