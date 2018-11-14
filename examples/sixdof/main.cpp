#include <time.h>

#include "SimInput.h"
#include "sim/sim.h"
#include "sim/TRefDict.h"
#include "util/xml/xml.h"

using namespace dsf::sim;
using namespace dsf::xml;

int main() 
{
	xml xmlinput("vehicle.xml");
		xmlinput.parse();

	xmlnode n = xmlnode(*xmlinput.xmlRoot).search("sim");

	Block * root = new Block;

		// Instantiate classes
	int nx = n.numchild();
	for ( int i = 0; i < nx; i++)
	{
		root->addChild( TRefUnique<Block>( n.child( i).attrAsString("id")));
		n.parent();
	}
	for ( int i = 0; i < nx; i++)
	{
		n.child( i).attrAsString("id");
		root->getChild(i)->configure( n);
		n.parent();
	}

		// Instantiate simulation
	Sim *sim = new Sim();
	SimInput input( n);
	sim->load(root, input.dt(), input.tmax(), input.rateConsole(), input.rateFile());
	sim->run();

	cin.get();
	return 0;
}