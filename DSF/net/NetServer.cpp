
#include "NetServer.h"
#include "data.h"
#include "../../examples/sixdof/EOM/EOMBase.h"

using namespace dsf::sim;
using namespace dsf::util;

Block* NetServer::block = TClass<NetServer,Block>::Instance()->getStatic();

NetServer::NetServer()
	: acceptor(io_service, tcp::endpoint(tcp::v4(), 6969)) // FIXME if this is part of DSF library, opening a socket every time you load library into memory!
{}

void NetServer::server_init()					// initalize a socket connection
{
	// TODO winsock initialized socket stream here
	// FIXME likely not be needed with asio
}

void NetServer::listen(/* int num_connections,*/)					// set up a conection for listening (bound to port)
{
	// TODO receive connection from client
}



void NetServer::get_xml_file()
{
	// TODO receive XML file

	// Receive XML file
	// FIXME instead of saving XML file, can you feed a stream into the xml configurator?
	ofstream xml("xml_received.xml",ios::out);
//	xml << buf;// << endl;		// note: chunks might not come in full lines need some sort of ACK method
	xml.close();
}

template<class T> void NetServer::send(T t)	// send a class of type T
{
	// TODO send struct to client
	// FIXME ...
	
/* ref code
	tcp::socket socket(io_service);
    acceptor.accept(socket);

    std::string message = make_daytime_string();

    boost::system::error_code ignored_error;
    boost::asio::write(socket, boost::asio::buffer(message), ignored_error);
*/
}

void NetServer::rpt()
{
	// On RPT call, update sim
	// NOTE: may want to recast at another frequency, update?

	data d;
/*
	d.x = rbeq->position().x;
	d.y = rbeq->position().y;
	d.z = rbeq->position().z;

	d.phi   = rbeq->Orientation().x;
	d.theta = rbeq->Orientation().y;
	d.psi   = rbeq->Orientation().z;
*/
	d.t = t();

	send<data>(d);
}
