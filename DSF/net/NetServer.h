#pragma once

#include "msg.h"

#include <boost/asio.hpp>
using boost::asio::ip::tcp;


#include "../sim/block.h"

#include "../util/math/vec3.h"
#include "../util/math/mat3.h"

class EarthBase;
class NetServer : public dsf::sim::Block
{
public:
	NetServer();		// req'd for class dictionary

	static Block *block;

	void set(EarthBase & r) // FIXME XML config...
	{
		this->rbeq = &r;
	};

	void server_init();					// initalize and start an inbound socket connection
	void listen();						// set up a conection for listening (bound to port)
	void get_xml_file();						// receive incoming xml file
 	template<class T> void send(T t);	// send a class of type T
	void rpt();

private:
	EarthBase * rbeq;
    boost::asio::io_service io_service;
	tcp::acceptor acceptor;
};