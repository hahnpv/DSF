/**
 * @file NetServer.h
 * @brief TCP server block for remote simulation data distribution.
 *
 * Listens for incoming TCP connections and streams telemetry data
 * (EOM state) to connected clients each simulation step.
 */
#pragma once

#include "msg.h"

#include <boost/asio.hpp>
using boost::asio::ip::tcp;

#include "../sim/block.h"

#include "../util/math/vec3.h"
#include "../util/math/mat3.h"

class EOMBase;

/**
 * @brief TCP server block for streaming telemetry to remote clients.
 *
 * Registers as a Block in the simulation tree and sends EOM state
 * data over TCP on each report cycle.
 */
class NetServer : public dsf::sim::Block
{
public:
	NetServer();                        ///< Default constructor (for factory registration).

	static Block *block;                ///< Factory registration handle.

	/**
	 * @brief Bind to an EOM instance for state extraction.
	 * @param r Reference to an EOMBase-derived object.
	 */
	void set(EOMBase & r)
	{
		this->rbeq = &r;
	};

	virtual void init();                ///< Initialize server socket.
	void server_init();                 ///< Set up inbound socket connection.
	void listen();                      ///< Listen for incoming connections.
	void get_xml_file();                ///< Receive XML configuration from client.
 	template<class T> void send(T t);   ///< Send typed data to connected client.
	void rpt();                         ///< Report (send telemetry each step).

private:
	EOMBase * rbeq;                     ///< Bound EOM instance for state data.
    boost::asio::io_service io_service; ///< Boost ASIO I/O service.
	tcp::acceptor acceptor;             ///< TCP acceptor for incoming connections.
};