/**
 * @file clock.h
 * @brief Digital simulation clock with integer-based time tracking.
 * 
 * Provides precise time management using integer ticks to avoid floating-point
 * round-off errors. Designed for RK4 integration (2 ticks per dt).
 */
#pragma once

#include <iostream>
#include <cmath>

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
            /// Default constructor for function-pointer use. All members are
            /// initialized so a Clock that is never load()'d is not indeterminate.
            Clock()
                : error(1.0), maxtime(0.0), safe_sample(true), time(0), state(true) {};

            /**
             * @brief Construct clock with integration rate.
             * @param _dt   Integration timestep [s].
             * @param _tmax Maximum simulation time [s].
             */
            Clock(double _dt, double _tmax)
            {
                time  = 0;
                error = (_dt > 0.0) ? (1/_dt)*2.0 : 1.0;	// guard divide-by-zero
                state = true;
                maxtime  = _tmax;
                safe_sample = true;	// not mid-integration until a step starts
            }

            /**
             * @brief Get current simulation time.
             *
             * Tick time plus the integrator's continuous stage offset. The
             * offset is nonzero only mid-integration (safe_sample == false),
             * where it carries the intra-step stage time that integer ticks
             * cannot represent (Dormand-Prince c = 1/5, 3/10, ...). At every
             * macro-step boundary it is identically zero, so sampled/reported
             * time remains pure tick arithmetic (no floating-point drift).
             * @return Time [s].
             */
            double t()              { return (double)time/error + stage_offset; }

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
                time  = (unsigned long) ( (double)time * derror + 0.5);	// round, not truncate
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
                if ( t < 0.0 )
                    return false;

                // Fire once per sample period, on the first step that enters a new
                // period. The old test required time/(t*error) to be an exact
                // integer double, which silently dropped every report when the
                // sample period was not a whole multiple of dt (e.g. rpt=0.1 with
                // dt=0.03). Comparing period indices across the step is robust to
                // any dt/rpt ratio.
                double now  = this->t();
                double prev = now - this->dt();
                const double eps = 1e-9;
                long period_now  = (long)std::floor(now  / t + eps);
                long period_prev = (long)std::floor(prev / t + eps);
                return period_now != period_prev;
            }

            void increment()        { time++; }             ///< Advance clock by dt/2.

            /**
             * @brief Set the continuous stage-time offset [s past tick time].
             *
             * Integrators call this before each stage derivative evaluation so
             * time-dependent models see the true stage time (t0 + c_i*h) even
             * when it falls between ticks (adaptive sub-steps, DP fractions).
             * Only meaningful mid-integration; set(true) resets it to zero.
             */
            void set_stage_offset(double s) { stage_offset = s; }

            /// Set integration state. Leaving integration (true) also clears
            /// the stage offset — sampled time is always pure tick time.
            void set(bool _safe_sample)
            {
                safe_sample = _safe_sample;
                if (_safe_sample) stage_offset = 0.0;
            }
            void end()              { state = false; }      ///< Signal simulation termination.
            bool is_running()       { return state; }       ///< Check if simulation should continue.

        private:
            double error;           ///< Tick-to-seconds conversion factor (2/dt).
            double maxtime;         ///< Maximum simulation time [s].
            bool safe_sample;       ///< True when not mid-integration step.
            unsigned long int time; ///< Current time in ticks.
            bool state;             ///< Simulation run state (true=running).
            /// Continuous intra-step stage time [s past tick time]. Appended
            /// LAST deliberately: a model library built against the old Clock
            /// layout reads the earlier fields correctly and its stale inline
            /// t() simply misses the offset (sees macro time — the pre-R2
            /// behavior) instead of corrupting memory. Rebuild model libs to
            /// get true stage times.
            double stage_offset = 0.0;
        };
    }
}
