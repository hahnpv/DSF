/**
 * @file block.h
 * @brief Base class for all simulation components in the DSF framework.
 * 
 * The Block class provides the fundamental lifecycle methods (init, update,
 * rpt, finalize) and graph topology support for hierarchical simulations.
 */
#pragma once

#include "clock.h"
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
            Block()                 { parent = nullptr; clock = nullptr; o = nullptr; rptRate = 0.0; };            ///< Default constructor; null pointers.
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

            /**
             * @brief Post-integration constraint hook.
             *
             * Called by the integrator exactly ONCE per macro step, after all
             * integrated states for the step have been committed and the clock
             * is at the end-of-step time — and before event evaluation and
             * reporting. This is the only place a block may legally:
             * - project integrated states onto constraints (ground/water
             *   contact, joint limits), and
             * - change discrete mode flags (e.g. on_ground) that update()
             *   reads, so that derivative evaluations are consistent across
             *   all stages of a step.
             *
             * update() must NEVER mutate integrated states or mode flags —
             * it runs once per integrator stage and such mutations corrupt
             * the integrator's assumptions (RK stages see inconsistent
             * dynamics). Default is a no-op.
             *
             * Integrator ordering guarantees:
             * - RK4:  constrain() runs after the final (pass-3) state commit,
             *         followed by one update() so derived outputs and the next
             *         step's derivatives reflect the constrained state.
             * - RK45: constrain() runs after the last accepted sub-step of the
             *         macro step (clock already advanced), followed by one
             *         update() for the same reason.
             * - Verlet: constrain() runs after the final half-kick commit;
             *         derived outputs refresh at the next step's first
             *         update() (the symplectic path adds no extra force
             *         evaluation).
             */
            virtual void constrain() {};
            virtual void rpt()      {};     ///< Output telemetry/reports.
            virtual void rptSim() { if( sample(rptRate) ) rpt(); }; ///< Conditional reporting based on sample rate.
            virtual void finalize() {};     ///< Cleanup at simulation end.
    
            /// @name Time Functions
            /// @{
            // These guard against a null clock: a Block that has not been added
            // to a loaded Sim (e.g. `dsf.Block().t()` from Python, or a block
            // created after Sim::load) has clock == nullptr. Returning a benign
            // value beats a segfault.
            double  t()             { return clock ? clock->t()  : 0.0; };  ///< Get current simulation time [s].
            double dt()             { return clock ? clock->dt() : 0.0; };  ///< Get integration timestep [s].
            void set_dt(double dt)  { if (clock) clock->set_dt( dt); };     ///< Modify timestep dynamically.
            void end(void)          { if (clock) clock->end(); };           ///< Signal simulation termination.
            bool sample(double t=0) { return clock ? clock->Sample(t) : false; };///< Check if current time is a reporting sample.
            /// @}

            /// @name Reference Functions
            /// @{
            void ClockRef(Clock *_clock) { if (clock == nullptr) clock = _clock; };   ///< Set clock reference (called by Sim).
            void OutputRef(Output *_o) { o = _o; };  ///< Set output reference.
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

        /**
         * @brief Warn about deck attributes a block's metadata does not declare.
         *
         * Compares the attribute names present on XML node `n` against the
         * property names class `blk` published via DSF_PROPERTY /
         * DSF_PROPERTY_BIND (see PropertyNameRegistry() in TClassDict.h) and
         * prints one warning line per unknown attribute — the classic typo'd
         * attribute that silently reads as 0.
         *
         * - Classes that publish no metadata at all are skipped (not
         *   checkable — absence of metadata does not mean absence of
         *   attributes).
         * - Framework-consumed attributes (id, class, name, rpt) are always
         *   allowed.
         *
         * Call sites: the deck loaders invoke this on every top-level block
         * right after configure() (C++ dynamic loader and the Python
         * SimSession), and container blocks that configure their own children
         * (e.g. sixdof's Vehicle) invoke it per child. Warnings are advisory
         * only; the strict-mode unused-attribute validation (validate.h)
         * remains the fatal check.
         */
        inline void warn_unknown_attributes(Block* blk, dsf::xml::xmlnode n)
        {
            if (!blk) return;

            // Attributes the framework itself consumes on block nodes:
            // id/class/name are read by the loaders (instantiation + naming),
            // rpt by Block::configure.
            static const std::set<std::string> framework_attrs =
                {"id", "class", "name", "rpt"};

            const auto& registry = PropertyNameRegistry();
            const std::string cls = boost::core::demangle(typeid(*blk).name());
            auto it = registry.find(cls);
            if (it == registry.end()) return;   // no metadata published — not checkable

            for (const std::string& attr : n.attrNames())
            {
                if (framework_attrs.count(attr)) continue;
                if (it->second.count(attr)) continue;
                std::cout << "WARNING: " << cls << " '" << blk->getName()
                          << "': unknown attribute '" << attr
                          << "' (not in metadata)" << std::endl;
            }
        }
    }
}