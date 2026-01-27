/**
 * @file log_level.h
 * @brief Definition of logging priority levels.
 */
#pragma once

namespace dsf
{
    namespace sim
    {
        enum LogLevel {
            LOG_CRITICAL = 0,   ///< Essential data (Flight Safety)
            LOG_NORMAL = 1,     ///< Standard telemetry
            LOG_VERBOSE = 2     ///< High-rate / Debug data
        };
    }
}
