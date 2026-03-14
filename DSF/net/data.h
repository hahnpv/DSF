/**
 * @file data.h
 * @brief POD struct for network telemetry transport.
 *
 * Simple plain-old-data struct for streaming vehicle state
 * (position + attitude + time) over TCP sockets.
 */
#pragma once

/// Network telemetry data packet.
struct ServerData
{
	double x;       ///< Position X [m].
	double y;       ///< Position Y [m].
	double z;       ///< Position Z [m].

	double phi;     ///< Roll angle [rad].
	double theta;   ///< Pitch angle [rad].
	double psi;     ///< Yaw angle [rad].
	
	double t;       ///< Simulation time [s].
};