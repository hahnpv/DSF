#pragma once

#include "net.h"
#include "msg.h"

#include "../sim/Block.h"

#include "../util/math/Vec3.h"
#include "../util/math/Mat3.h"

class Rbeom;
class netmon : public dsf::sim::Block
{
public:
	netmon() {};		// req'd for class dictionary

	static Block *block;

	void set(Net & n, Rbeom & r)
	{
		this->net = &n;
		this->rbeq = &r;
	};
	void rpt();
private:
	Net * net;
	Rbeom * rbeq;
};