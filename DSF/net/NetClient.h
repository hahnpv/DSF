#pragma once

#include <iostream>

#include <boost/asio.hpp>
using boost::asio::ip::tcp;


// client, currently used by vis, to get visalization in real time

struct data;

class NetClient
{
public:
	NetClient();
	void connect(std::string, int);				// connect to a remote host (PORT)

	void send_xml_file(std::string filename);		// send xml data to connected host
	template<class T> T receive();				// compliment to send

	// clean up
	void close();

private:
    boost::asio::io_service io_service;
};