/**
 * @file number.h
 * @brief NaN and infinity detection utilities (pre-C++11 fallback).
 *
 * @deprecated C++11 provides std::isnan() and std::isinf() in <cmath>.
 *             Prefer those over these custom implementations.
 */
#pragma once

#include <iostream>
#include <limits>
#include "quat.h"

namespace dsf
{
	namespace util
	{
        /// Check if a value is NaN (uses the self-inequality trick).
        template<typename T>
        inline bool isnan(T value)
        {
            return value != value;
        }

        /// Check if a value is positive infinity.
        template<typename T>
        inline bool isinf(T value)
        {
            return std::numeric_limits<T>::has_infinity && (value == std::numeric_limits<T>::infinity());
        }
    }
}