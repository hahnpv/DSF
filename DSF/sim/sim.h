/**
 * @file sim.h
 * @brief Top-level simulation executive.
 *
 * Sim owns the main simulation loop: it advances the clock, calls the
 * integrator, fires reports, and checks termination conditions. A single
 * Sim instance manages one block-tree + clock + output chain.
 *
 * ## Usage
 * @code{.cpp}
 * dsf::sim::Sim sim;
 * sim.load(root_block, 0.01, 600.0, 1.0, 0.1);
 * sim.run();
 * @endcode
 */
#pragma once

#include "output.h"
#include "event.h"
#include "TIntDict.h"
#include <vector>
#include <string>

namespace dsf
{
    namespace sim 
    {
        class Clock;
        class IntegratorBase;
        class Block;

        /**
         * @brief Simulation executive — owns the run loop.
         *
         * Manages the clock, integrator, output, and the root block tree.
         * Provides two load() overloads: one for fixed-step RK4 and one
         * for selectable integrator type with adaptive tolerances.
         */
        class Sim {
        public:
            /// Release the Sim-owned clock, output, and integrator. The
            /// root block tree is caller-owned and is NOT deleted.
            ~Sim();

            /// Run the complete simulation (init → loop → finalize).
            void run();

            /// Initialize all blocks (calls Block::init on the tree).
            void init();

            /// Advance one integration step.
            void step();

            /// Finalize all blocks and close output files.
            void finalize();

            /// Set XML file info for HDF5 metadata and filename convention.
            void setXmlInfo(const std::string& xml_file, const std::string& xml_content);

            /// Execute the main simulation loop (step until tmax or end()).
            void exec();

            /**
             * @brief Load simulation with default RK4 integrator.
             * @param simulation Root block of the simulation tree.
             * @param dt         Integration timestep [s].
             * @param tmax       Maximum simulation time [s].
             * @param console    Console output rate [s].
             * @param file       File output rate [s].
             */
            void load(Block * simulation, double dt, double tmax, double console, double file);

            /**
             * @brief Load simulation with selectable integrator.
             * @param simulation      Root block of the simulation tree.
             * @param dt              Integration timestep [s].
             * @param tmax            Maximum simulation time [s].
             * @param console         Console output rate [s].
             * @param file            File output rate [s].
             * @param integrator_type Integrator name: "RK4", "RK45", or "Verlet".
             * @param atol            Absolute tolerance (RK45 only).
             * @param rtol            Relative tolerance (RK45 only).
             */
            void load(Block * simulation, double dt, double tmax, double console, double file,
                      const std::string& integrator_type, double atol = 1e-8, double rtol = 1e-6);

            /// Returns the simulation vector, used by Integrator to get a handle on the sim vector for derivatives.
            std::vector<Block*> sim()
            {
                return simulation;
            };

            Clock *clock = nullptr;                 ///< Simulation clock.
            Output *output = nullptr;               ///< Telemetry output handler.

            /// This Sim's OWN integrand registry and event bus (R1 — no more
            /// process-global mutable state). Made "current" (thread_local)
            /// for the duration of load/init/step/exec/finalize, so model
            /// code calling the Instance() accessors lands here.
            TClassIntegrandDict<Block>* integrands() { return &integrands_; }
            EventBus* events() { return &events_; }

        private:
            TClassIntegrandDict<Block> integrands_; ///< Sim-owned integrands [R1].
            EventBus events_;                       ///< Sim-owned event bus [R1].
            double rptRate = 0.0;                   ///< Console report rate [s].
            std::vector<Block*>simulation;          ///< Root block tree.
            IntegratorBase *i = nullptr;            ///< Active integrator.
        };
    }
}