/**
 * @file block.h
 * @brief Base class for all simulation components in the DSF framework.
 * 
 * The Block class provides the fundamental lifecycle methods (init, update,
 * rpt, finalize) and graph topology support for hierarchical simulations.
 */
#pragma once

#include "clock.h"
#include "RTclock.h"
#include <vector>

#include "../util/xml/xml.h"

#include "TClassDict.h"

namespace dsf
{
    namespace sim 
    {
        class Output;
        class Clock;

        /**
         * @brief Base class for all simulation model blocks.
         * 
         * Block is the fundamental building block of DSF simulations. All model
         * components inherit from Block and implement its lifecycle methods.
         * Blocks can form a tree hierarchy via parent/child relationships.
         * 
         * ## Lifecycle Methods
         * - `configure()`: Parse XML configuration
         * - `init()`: Initialize state variables
         * - `update()`: Propagate dynamics (called by integrator)
         * - `rpt()`: Output telemetry
         * - `finalize()`: Cleanup at simulation end
         * 
         * ## Usage
         * @code{.cpp}
         * class MyModel : public dsf::sim::Block {
         * public:
         *     static Block *block;  // For factory registration
         *     virtual void configure(dsf::xml::xmlnode n);
         *     virtual void update();
         * };
         * // Register with factory:
         * Block* MyModel::block = TClass<MyModel, Block>::Instance();
         * @endcode
         */
        class Block 
        {
        public:
            Block()                 { parent = 0; };            ///< Default constructor; null parent pointer.
            virtual ~Block()        {};                         ///< Destructor.
            
            /**
             * @brief Configure block from XML.
             * @param n XML node containing block configuration.
             */
            virtual void configure(dsf::xml::xmlnode n)
            {
                rptRate = n.attrAsDouble("rpt");
                name = n.parent().attrAsString("name");
            }
            
            virtual void init()     {};     ///< Initialize state variables and integrators.
            virtual void update()   {};     ///< Update dynamics (called each integration step).
            virtual void rpt()      {};     ///< Output telemetry/reports.
            virtual void rptSim() { if( sample(rptRate) ) rpt(); }; ///< Conditional reporting based on sample rate.
            virtual void finalize() {};     ///< Cleanup at simulation end.
    
            /// @name Time Functions
            /// @{
            double  t()             { return clock->t();  };    ///< Get current simulation time [s].
            double dt()             { return clock->dt(); };    ///< Get integration timestep [s].
            void set_dt(double dt)  { clock->set_dt( dt); };    ///< Modify timestep dynamically.
            void end(void)          { clock->end(); };          ///< Signal simulation termination.
            bool sample(double t=0) { return clock->Sample(t); };///< Check if current time is a reporting sample.
            /// @}

            /// @name Reference Functions
            /// @{
            void ClockRef(Clock *_clock) { clock = _clock; };   ///< Set clock reference (called by Sim).
            void OutputRef(Output *_o) { o = _o; };             ///< Set output reference (called by Sim).
            /// @}

            /// @name Graph Topology Functions
            /// @{
            
            /**
             * @brief Add a child block to this block.
             * @param b Pointer to child block.
             */
            void addChild( Block *b)
            {
                b->parent = this;
                children.push_back( b);
            }
            /**
             * @brief Remove a child block from this block.
             * @param b Pointer to child block to remove.
             */
            virtual void removeChild(Block *b)
            {
                for (std::vector<Block*>::iterator it = children.begin(); it != children.end(); )
                {
                    if (*it == b)
                    {
                        (*it)->parent = NULL;
                        it = children.erase(it);
                    }
                    else
                    {
                        ++it;
                    }
                }
            }
            
            /**
             * @brief Check if block has children.
             * @return True if children exist.
             */
            bool has_children()
            {
                if (children.size() != 0)
                    return true;
                else
                    return false;
            }
            
            Block * getParent() { return parent; };                     ///< Get parent block.
            Block * getChild(int i) { return children[i]; };            ///< Get child by index.
            std::vector< Block *> getChildren() { return children; };   ///< Get all children.
            std::string getName() { return name; };                     ///< Get block instance name.
            void setName(std::string _name) { name = _name; };          ///< Set block instance name.
            /// @}

        protected:
            std::vector< Block *>children;  ///< Child blocks vector.
            Block * parent;                 ///< Parent block pointer.
            Output *o;                      ///< Output handler reference.
            Clock *clock;                   ///< Simulation clock reference.
            double rptRate;                 ///< Report sample rate [s].
            std::string name;               ///< Block instance name.
        };
        extern template class TClassDict<Block>;
    }
}