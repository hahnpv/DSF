/**
 * @file WindowsSockets.h
 * @brief Windows-only WinSock initialization helper.
 *
 * Not used on Linux — included only for cross-platform compatibility.
 */
#pragma once

#include <winsock.h>
#include <iostream>

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