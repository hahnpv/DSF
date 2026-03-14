/**
 * @file msg.h
 * @brief Templated message wrapper for network transport.
 *
 * Wraps an arbitrary type T into a struct with operator() for
 * value extraction, used by NetServer/NetClient for typed messaging.
 */
#pragma once

/**
 * @brief Templated network message container.
 * @tparam T Payload type.
 */
template<class T>
struct msg
{
	/// Extract the payload.
	T operator()()
	{
		return t;
	}
	T t;    ///< Payload data.
};