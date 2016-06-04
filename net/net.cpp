#include "net.h"
#include "data.h"
#include <iostream>
#include <fstream>			// file i/o test
#include <string>

#include "WindowsSockets.h"
#include "to_string.h"

using namespace std;
#define BACKLOG 10     // how many pending connections queue will hold
#define MAXDATASIZE 100 // max number of bytes we can get at once 
Net::Net(int port)
{
	if (WIN32)
	{
		WS_Start();
	}

	this->port = port;
}
void Net::connect(std::string location, int PORT)					// connect to a remote host
{

    struct hostent *he;
    struct sockaddr_in their_addr; // connector's address information 

    if ((he=gethostbyname(location.c_str())) == NULL) {  // get the host info 
     //   herror("gethostbyname");
		cout << "ERROR:  can't get host" << endl;
		cin.get();
        exit(1);
    }
	if ((sockfd = ::socket(PF_INET, SOCK_STREAM, 0)) == -1) {
        perror("socket");
		cin.get();
        exit(1);
    }

    their_addr.sin_family = AF_INET;    // host byte order 
    their_addr.sin_port = htons(PORT);  // short, network byte order 
    their_addr.sin_addr = *((struct in_addr *)he->h_addr);
    memset(their_addr.sin_zero, '\0', sizeof their_addr.sin_zero);

	if (::connect(sockfd, (struct sockaddr *)&their_addr,sizeof their_addr) == -1) {
        perror("connect");
		cin.get();
        exit(1);
    } 
}
void Net::server_init()					// initalize a socket connection
{
	// defaults to socket stream, make it customizable
	if ((socket = ::socket(PF_INET, SOCK_STREAM, 0)) == -1) 
	{
        perror("socket");
		cin.get();
        exit(1);
    }

	char yes = '1';
	if (setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(char)) == -1) 
	{
        perror("setsockopt");
		cin.get();
        exit(1);
    }

	// set up my network stuff
	my_addr.sin_family = AF_INET;         // host byte order
    my_addr.sin_port = htons(port);     // short, network byte order
    my_addr.sin_addr.s_addr = INADDR_ANY; // automatically fill with my IP
    memset(my_addr.sin_zero, '\0', sizeof my_addr.sin_zero);

    if (bind(socket, (struct sockaddr *)&my_addr, sizeof my_addr) == -1) {
        perror("bind");
		cin.get();
        exit(1);
    }

	if (::listen(socket, BACKLOG) == -1) {
        perror("listen");
		cin.get();
        exit(1);
    }
}
void Net::listen(/* int num_connections,*/)					// set up a conection for listening (bound to port)
{
		//	sockets = new int[num_connections-1];
	//
	//	In a server architecture this would loop to accept incoming clients,
	//	then spawn a worker thread to communicate with the clients 1:1
	//
		cout << "..." << endl;
        int sin_size = sizeof their_addr;
        if ((sockfd = accept(socket, (struct sockaddr *)&their_addr, &sin_size)) == -1) { 
            perror("accept");
 //           continue;
        }
        printf("server: got connection from %s\n", inet_ntoa(their_addr.sin_addr));
		// fork process ...

}

void Net::get_xml_file()
{
	int numbytes;
	char buf[MAXDATASIZE];

	// Receive XML file
		ofstream xml("xml_received.xml",ios::out);

		while (1)
		{
			if ((numbytes=recv(sockfd, buf, MAXDATASIZE-1, 0)) == -1) 
			{
				if (::send(sockfd, "ACK\n", 4, 0) == -1)
				{
					perror("send");
					// error on receive, we pinged back to the client, not able to hit, so exit this loop.
					// this while() loop needs to be made into a thread
					break;
				}
				perror("recv");
			}
			else
			{
//				if (buf[0] != 'E' && buf[1] != 'O' && buf[2] != 'F')
//				{
				bool eof = false;
				buf[numbytes] = '\0';
				for (int i=0; i<numbytes; i++)
				{
					if (buf[i] == 'E')
						if (buf[i+1] == 'O')
							if (buf[i+2] == 'F')
							{
								cout << endl << "EOF found" << endl;
								buf[i] = '\0';
								for (int j=i+1; j<numbytes; j++)
									buf[j] = ' ';
								eof = true;
							}
				}
//					printf("Received: %s",buf);
				if (DBG)
					cout << "Received: " << buf << endl;
				xml << buf;// << endl;		// note: chunks might not come in full lines need some sort of ACK method
											// right now looks OK but over internet/routers/etc might get broken
				if (eof)
				{
					if (DBG)
						cout << "breaking xml read" << endl;
					break;
				}
			}
		}	
		xml.close();
}
void Net::send_xml_file(std::string filename)
{
	// try streaming an XML file
	ifstream xml(filename.c_str(),ios::in);
	std::string line;
	while( !xml.eof())
	{
		getline(xml,line);
		if (DBG)
			cout << "sending" << line << endl;

		// add a newline constant to each line
		line.append("\n");
		if (::send(sockfd, line.c_str(), line.length(), 0) == -1)
		{
			perror("send");
		}
	}
	xml.close();
	if (::send(sockfd, "EOF", 3, 0) == -1)
	{
		perror("send");
	}
}
void Net::close()
{
	WSACleanup();
}