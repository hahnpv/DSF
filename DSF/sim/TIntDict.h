/**
 * @file TIntDict.h
 * @brief Integrand dictionary for numerical integration.
 * 
 * Stores state-derivative pairs for the integrator. Blocks register their
 * state variables here to be automatically integrated each timestep.
 */
#pragma once

#include <vector>
#include <typeinfo>
#include <exception>
#include <iostream>
#include <string>
#include "integrator_base.h"  // for IntegrandType
#include "../util/math/quat.h"   // for Quaternion integrand support

using namespace std;

namespace dsf
{
    namespace sim 
    {
        // Forward declaration
        template<class base> class TClassBase;

        /**
         * @brief Singleton dictionary of integrands for numerical integration.
         * 
         * Blocks register state variables and their derivatives with this dictionary.
         * The integrator iterates over all registered pairs each timestep.
         * 
         * @tparam TClass Base class type (usually Block).
         * 
         * ## Usage
         * @code{.cpp}
         * // In block's init():
         * TClassIntegrandDict<Block>::Instance()->add(this, x, dx);
         * TClassIntegrandDict<Block>::Instance()->add(this, position, velocity);
         * @endcode
         */
        template <class TClass> class TClassIntegrandDict
        {
        public:
            /**
             * @brief Get singleton dictionary instance.
             * @return Pointer to singleton.
             */
            static TClassIntegrandDict<TClass> * Instance()
            {
                if (SingletonInstance == NULL)
                {
                    SingletonInstance = new TClassIntegrandDict<TClass>;
                }
                return SingletonInstance;
            };

            /**
             * @brief Register a Vec3 state-derivative pair.
             * @param in Owner block.
             * @param v  State vector.
             * @param dv Derivative vector.
             */
            void add(TClassBase<TClass > *in, dsf::util::Vec3 &v, dsf::util::Vec3 &dv,
                     dsf::sim::IntegrandType type = dsf::sim::IntegrandType::GENERIC)
            {
                for (int i=0; i<3; i++)
                    addToIntegrator(in, v[i], dv[i], type);
            }

            /**
             * @brief Register a Mat3 state-derivative pair.
             * @param in Owner block.
             * @param m  State matrix.
             * @param dm Derivative matrix.
             * @param type IntegrandType tag (default GENERIC).
             */
            void add(TClassBase<TClass > *in, dsf::util::Mat3 &m, dsf::util::Mat3 &dm,
                     dsf::sim::IntegrandType type = dsf::sim::IntegrandType::GENERIC)
            {
                for (int i=0; i<3; i++)
                    for (int j=0; j<3; j++)
                        addToIntegrator(in, m[i][j], dm[i][j], type);
            }

            /**
             * @brief Register a Quaternion state-derivative pair.
             * @param in Owner block.
             * @param q  State quaternion.
             * @param dq Derivative quaternion.
             * @param type IntegrandType tag (default GENERIC).
             */
            void add(TClassBase<TClass > *in, dsf::util::Quaternion &q, dsf::util::Quaternion &dq,
                     dsf::sim::IntegrandType type = dsf::sim::IntegrandType::GENERIC)
            {
                addToIntegrator(in, q.q0, dq.q0, type);
                addToIntegrator(in, q.q1, dq.q1, type);
                addToIntegrator(in, q.q2, dq.q2, type);
                addToIntegrator(in, q.q3, dq.q3, type);
            }

            /**
             * @brief Register a scalar state-derivative pair.
             * @param in Owner block.
             * @param x  State value.
             * @param dx Derivative value.
             * @param type IntegrandType tag (default GENERIC).
             */
            void add(TClassBase<TClass > *in, double &x, double &dx,
                     dsf::sim::IntegrandType type = dsf::sim::IntegrandType::GENERIC)
            {
                addToIntegrator(in, x, dx, type);
            }

            /**
             * @brief Internal method to add to integrator storage.
             * @param in Owner block.
             * @param x  State reference.
             * @param dx Derivative reference.
             */
            void addToIntegrator(TClassBase<TClass > *in, double &x, double &dx,
                                 dsf::sim::IntegrandType type = dsf::sim::IntegrandType::GENERIC) 
            {
                double *x_ptr, *dx_ptr;
                 x_ptr =  &x;
                dx_ptr = &dx;

                this->x.push_back(  x_ptr );
                this->xd.push_back( dx_ptr );

                this->x0.push_back ( 0 );

                for (size_t s = 0; s < xdd.size(); s++)
                    xdd[s].push_back(0);
                
                this->types.push_back(type);
                classDict.push_back( *in);
            }

            /// Resize the intermediate stage storage (called by integrator at load time).
            /// Default is 4 (RK4). RK45 needs 6, Verlet needs 2.
            void resize_stages(int n_stages)
            {
                xdd.resize(n_stages);
                for (auto& stage : xdd)
                    stage.resize(x.size(), 0.0);
            }

            /// Remove all registered integrands. Called by Sim::load so that a
            /// second run in a long-lived process (GUI / MCP session / Monte
            /// Carlo) does not keep integrating the previous run's (freed) state
            /// pointers. Without this the integrator dereferences dangling memory.
            void clear()
            {
                x.clear();
                x0.clear();
                xd.clear();
                for (auto& stage : xdd)
                    stage.clear();
                types.clear();
                classDict.clear();
            }

            /// Remove every integrand whose state pointer lies in [lo, hi).
            /// Used to retire a body from the integrator at runtime — e.g. a
            /// spent stage that impacts ("pops") — so the integrator stops
            /// touching its state. `lo`/`hi` are typically the memory footprint
            /// of the retiring EOM object (its state vars are members).
            void removeInRange(const void* lo, const void* hi)
            {
                for (size_t i = 0; i < x.size(); )
                {
                    const void* p = static_cast<const void*>(x[i]);
                    if (p >= lo && p < hi)
                    {
                        x.erase(x.begin() + i);
                        x0.erase(x0.begin() + i);
                        xd.erase(xd.begin() + i);
                        for (auto& stage : xdd)
                            if (i < stage.size()) stage.erase(stage.begin() + i);
                        types.erase(types.begin() + i);
                        classDict.erase(classDict.begin() + i);
                    }
                    else ++i;
                }
            }

        private:
            TClassIntegrandDict()
            {
                xdd.resize(4);
            }
        public:
            std::vector<double*>x;                          ///< State value pointers.
            std::vector<double>x0;                          ///< Initial values (start of step).
            std::vector<double*>xd;                         ///< Derivative pointers.
            std::vector< std::vector<double> > xdd;         ///< Intermediate stage values.
            std::vector<dsf::sim::IntegrandType> types;     ///< Per-integrand type tags.
            std::vector<TClassBase<TClass > >classDict;     ///< Owner blocks for each integrand.
            static TClassIntegrandDict<TClass> * SingletonInstance; ///< Singleton pointer.
        };
        /// Static member initialization
        template<class TClass> TClassIntegrandDict<TClass> * TClassIntegrandDict<TClass>::SingletonInstance =0;
    }
}
