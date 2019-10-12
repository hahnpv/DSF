#ifndef NUMBER_H
#define NUMBER_H
#include <iostream>
#include "quat.h"
//class Quaternion;
namespace dsf
{
	namespace util
	{
        
        template<typename T>
        inline bool isnan(T value)
        {
            return value != value;
        }

        #include <limits>
        template<typename T>
        inline bool isinf(T value)
        {
            return std::numeric_limits<T>::has_infinity && (value == std::numeric_limits<T>::infinity());
        }
    }
}
#endif