#pragma once

#include "util/xml/xml.h"

// test xmlnode
#include "util/xml/xmlnode.h"

//
//	Input an XML file, parse it, get relevant bits
//  and update mass properties model
//

class MassInput
{
public:
	MassInput(node n)
	{
		// presuming we get the mass node
		parse(n);
	}

	void parse(node n)
	{
		// presuming the only nodes of mass are stages.

		// loop over all stages
		for (unsigned int i=0; i< n.child.size(); i++)
		{
			// create a stage 
			vehicle.resize(i+1);		// size outside of loop according to child.size()
			cout << "vehicle size: " << vehicle.size() << endl;
			// loop over all elements
			for (unsigned int j=0; j < n.child[i]->child.size(); j++)
			{
				// make an xml node
				xmlnode nn(*n.child[i]->child[j]);

				// create a component
				double mass   = nn.attrAsDouble("mass");
				Vec3 position = nn.attrAsVec3("position");
				Mat3 MOI      = nn.attrAsMat3("MOI");
				// add to stage
				vehicle[i].push_back( Component(position,MOI,mass));
			}		
		}
	}
		// return the entire vehicle vector
	std::vector< std::vector< Component>>get_vehicle()
	{
		return vehicle;
	}
private:
	std::vector< std::vector< Component>>vehicle;
};