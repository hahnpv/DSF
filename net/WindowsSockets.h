#pragma once
#ifdef WINDOWS
#include <winsock.h>
#include <iostream>
// Handles all of the Windows Sockets stuff (WSAblah)

void WS_Start()
{
    WSADATA wsaData;   // if this doesn't work
    if (WSAStartup(MAKEWORD(1, 1), &wsaData) != 0) 
	{
		std::cout << "WSAStartup failed" << stderr << std::endl;
    }
	else
	{
		std::cout << "WSAStartup Success!" << std::endl;
	}
}
#endif
