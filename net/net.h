#pragma once

#include <winsock.h>
#include <iostream>

//internalize sockfd

// a network class, server-specific.
#define MAXDATASIZE 100 // max number of bytes we can get at once 
struct data;

#define DBG 0				// hax. fake bool for debug output
							// make fancier later

class Net
{
public:
	Net(int port);
	void server_init();					// initalize and start an inbound socket connection
	void connect(std::string, int);					// connect to a remote host (PORT)
	void listen();						// set up a conection for listening (bound to port)

	template<class T> void send(T t)	// send a class of type T
	{
		// new, templated message to abstract packaging from user
		msg<T> m;
		m.t = t;

		char buf[100];
		bool sent = false;
		if (DBG)	
			cout << "send size: " << sizeof(msg<T>) << endl;
		while(!sent)
		{
	//		if (::send(sockfd, (char *)&t, sizeof(T), 0) == -1)
			if (::send(sockfd, (char *)&m, sizeof(msg<T>), 0) == -1)
			{
				perror("send");
			}
				// wait for client confirmation "A" ack, "R" resend
			if (recv(sockfd, buf, MAXDATASIZE-1, 0) == -1) 
			{
				cout << "error receiving ack packet" << endl;
			}
			else
			{
				if (buf[0] == 'R')
				{
					if (DBG)
						cout << "Received ACK, re-sending" << endl;
				}
				else if (buf[0] == 'A')
				{
					if (DBG)
						cout << "Receipt of data confirmed" << endl;
					sent = true;
				}
			}
		}
	}
	template<class T> T receive()				// compliment to send
	{
		msg<T> m;
		//T t;
		bool received = false;
		if (DBG)
			cout << "receive size: " << sizeof(msg<T>) << endl;
		while (!received)
		{
			// works
			if (DBG)
				cout << "listening" << endl;
//			if (recv(sockfd, (char *)&t, sizeof(T), 0) == -1) 
			if (recv(sockfd, (char *)&m, sizeof(msg<T>), 0) == -1) 
			{
				cout << "Error on receive, requesting a re-send" << endl;
				if (::send(sockfd, "R\n", 2, 0) == -1)		// request re-send
				{
					perror("send");
					cout << "Error sending ACK" << endl;

					// error on receive, we pinged back to the client, not able to hit, (connection lost) so exit this loop.
					// this while() loop needs to be made into a thread
				}
				perror("recv");
			}
			else
			{
				if (::send(sockfd, "A\n", 2, 0) == -1)
				{
					perror("send");
					cout << "Error sending CONF" << endl;

					// need to try to re-send ... 
					// error on receive, we pinged back to the client, not able to hit, (connection lost) so exit this loop.
					// this while() loop needs to be made into a thread
				}
				break;
			}
		}
		return m.t;
	}

	void send_xml_file(std::string filename);		// send xml data to connected host
	void get_xml_file();			// receive incoming xml file

	// clean up
	void close();

private:
	int port;				// primary incoming port

//	int *sockets;		// socket array for forked connections, to be set in constructor
	
	int socket;			// socket id for incoming connections (server only)
	int sockfd;			// socket file descriptor, used by client
						// used by server after incoming connection is negotiated
						// (until multiple threads implemeted)

	struct sockaddr_in my_addr;    // my address information
    struct sockaddr_in their_addr; // connector's address information
};