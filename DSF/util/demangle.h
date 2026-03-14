/**
 * @file demangle.h
 * @brief GCC/Clang ABI type name demangling utility.
 */
#pragma once

#include <cxxabi.h>
#include <memory>
#include <string>

namespace dsf {
namespace util {
    // Helper function to demangle type names using GCC/Clang ABI
    inline std::string demangle(const char* name) {
        int status = 0;
        std::unique_ptr<char, void(*)(void*)> res {
            abi::__cxa_demangle(name, nullptr, nullptr, &status),
            std::free
        };
        return (status == 0) ? res.get() : name;
    }
} // namespace util
} // namespace dsf
