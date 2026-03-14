/**
 * @file NetClient.h
 * @brief TCP client block for connecting to a remote simulation server.
 *
 * Used by visualization or monitoring tools to receive real-time
 * telemetry from a running DSF simulation via TCP.
 */
#pragma once

#include <iostream>

#include <boost/asio.hpp>
using boost::asio::ip::tcp;

struct data;

/**
 * @brief TCP client for receiving simulation telemetry.
 */
class NetClient
{
public:
	NetClient();                                    ///< Default constructor.

	/**
	 * @brief Connect to a remote simulation server.
	 * @param host Hostname or IP address.
	 * @param port TCP port number.
	 */
	void connect(std::string host, int port);

	/**
	 * @brief Send an XML configuration file to the connected server.
	 * @param filename Path to XML file.
	 */
	void send_xml_file(std::string filename);

	/**
	 * @brief Receive typed data from the server.
	 * @tparam T Data type to receive (must match server's send type).
	 * @return Received data.
	 */
	template<class T> T receive();

	/// Close the connection.
	void close();

private:
    boost::asio::io_service io_service;     ///< Boost ASIO I/O service.
};