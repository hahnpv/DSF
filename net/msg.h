#pragma once

// message packet - can use the same templated interfaces as data, in theory, and
// easier than deconstructing/reconstructing strings, etc.
// haven't validated yet
/*
struct msg
{
	std::string operator()()
	{
		return message;
	}
	std::string message;
};
*/
template< class T>
struct msg
{
	T operator()()
	{
		return t;
	}
	T t;
};