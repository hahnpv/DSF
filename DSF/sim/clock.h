/**
 * @file clock.h
 * @brief Digital simulation clock with integer-based time tracking.
 * 
 * Provides precise time management using integer ticks to avoid floating-point
 * round-off errors. Designed for RK4 integration (2 ticks per dt).
 */
#pragma once

#include <iostream>

namespace dsf
{
    namespace sim 
    {
        /**
         * @brief Digital simulation clock with integer time tracking.
         * 
         * Uses integer tick counts internally to eliminate cumulative floating-point
         * errors. Time is converted to seconds via an error factor derived from dt.
         * 
         * ## Design Notes
         * The clock increments twice per RK4 integration step, so `error = 2/dt`.
         * This allows precise sample time detection for output and control loops.
         */
        class Clock
        {
        public:
            Clock() {};             ///< Default constructor for function pointer use.

            /**
             * @brief Construct clock with integration rate.
             * @param _dt   Integration timestep [s].
             * @param _tmax Maximum simulation time [s].
             */
            Clock(double _dt, double _tmax) 
            {
                time  = 0;
                error = (1/_dt)*2.0;
                state = true;
                maxtime  = _tmax;
            }

            /**
             * @brief Get current simulation time.
             * @return Time [s].
             */
            double t()              { return (double)time/error; }

            /**
             * @brief Get maximum simulation time.
             * @return Max time [s].
             */
            double tmax()           { return maxtime; }

            /**
             * @brief Change integration timestep dynamically.
             * 
             * @warning Only call when not mid-integration (Sample(0) == true).
             * @param newdt New integration rate [s].
             */
            void set_dt(double newdt)
            {
                if (!Sample(0.))
                    return;
                double derror =0;
                if ( (derror = (1/newdt)*2.0) == error)
                    return;
                derror /= error;
                error = (1/newdt)*2.0;
                time  = (int) ( (double)time * derror); 
            }

            /**
             * @brief Get current integration timestep.
             * @return Timestep [s].
             */
            double dt()             { return 2.0/error; }

            /**
             * @brief Check if current time is a sample point.
             * 
             * If t=0, returns true when not mid-integration.
             * If t!=0, returns true when current time is a multiple of t.
             * 
             * @param t Sample period to check [s]. Use 0 to check integration state.
             * @return True if this is a sample point.
             */
            bool Sample(double t)
            {
                if ( t == 0 || !safe_sample)
                    return safe_sample;
                if ( time / (t*error) == (int)(time / (t*error)) )
                    return true;
                else
                    return false;
            }

            void increment()        { time++; }             ///< Advance clock by dt/2.
            void set(bool _safe_sample) { safe_sample = _safe_sample; } ///< Set integration state.
            void end()              { state = false; }      ///< Signal simulation termination.
            bool is_running()       { return state; }       ///< Check if simulation should continue.

        private:
            double error;           ///< Tick-to-seconds conversion factor (2/dt).
            double maxtime;         ///< Maximum simulation time [s].
            bool safe_sample;       ///< True when not mid-integration step.
            unsigned long int time; ///< Current time in ticks.
            bool state;             ///< Simulation run state (true=running).
        };
    }
}
