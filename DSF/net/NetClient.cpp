#include "NetClient.h"
#include "data.h"
#include "msg.h"
#include <iostream>
#include <fstream>			// file i/o test
#include <string>

using namespace std;

/* note 
#pragma once
#include <iostream>
#include <sstream>
template <class T>
inline std::string to_string (const T& t)
{
	std::stringstream ss;
	ss << t;
	return ss.str();
}
*/


NetClient::NetClient()
{}

void NetClient::connect(std::string location, int PORT)					// connect to a remote host
{
	// TODO connect to server
}

void NetClient::send_xml_file(std::string filename)
{
	// TODO send XML config file

	ifstream xml(filename.c_str(),ios::in);
	std::string line;
	while( !xml.eof())
	{
		getline(xml,line);

		// add a newline constant to each line
		line.append("\n");
		// FIXME send line here
//		if (::send(sockfd, line.c_str(), line.length(), 0) == -1)
//		{
//			perror("send");
//		}
	}
	xml.close();
//	if (::send(sockfd, "EOF", 3, 0) == -1)
//	{
//		perror("send");
//	}

}

template<class T> T NetClient::receive()				// compliment to send
{
	// TODO receive data
	msg<T> m;
	//T t;
	bool received = false;
	return m.t;
}

void NetClient::close()
{}