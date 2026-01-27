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
            void add(TClassBase<TClass > *in, dsf::util::Vec3 &v, dsf::util::Vec3 &dv)
            {
                for (int i=0; i<3; i++)
                    addToIntegrator(in, v[i], dv[i]);
            }

            /**
             * @brief Register a Mat3 state-derivative pair.
             * @param in Owner block.
             * @param m  State matrix.
             * @param dm Derivative matrix.
             */
            void add(TClassBase<TClass > *in, dsf::util::Mat3 &m, dsf::util::Mat3 &dm)
            {
                for (int i=0; i<3; i++)
                    for (int j=0; j<3; j++)
                        addToIntegrator(in, m[i][j], dm[i][j]);
            }

            /**
             * @brief Register a scalar state-derivative pair.
             * @param in Owner block.
             * @param x  State value.
             * @param dx Derivative value.
             */
            void add(TClassBase<TClass > *in, double &x, double &dx)
            {
                addToIntegrator(in, x, dx);
            }

            /**
             * @brief Internal method to add to integrator storage.
             * @param in Owner block.
             * @param x  State reference.
             * @param dx Derivative reference.
             */
            void addToIntegrator(TClassBase<TClass > *in, double &x, double &dx) 
            {
                double *x_ptr, *dx_ptr;
                 x_ptr =  &x;
                dx_ptr = &dx;

                this->x.push_back(  x_ptr );
                this->xd.push_back( dx_ptr );

                this->x0.push_back ( 0 );

                this->xdd[0].push_back(0);
                this->xdd[1].push_back(0);
                this->xdd[2].push_back(0);
                this->xdd[3].push_back(0);
                classDict.push_back( *in);
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
            std::vector< std::vector<double> > xdd;         ///< RK4 intermediate values (k1-k4).
            std::vector<TClassBase<TClass > >classDict;     ///< Owner blocks for each integrand.
            static TClassIntegrandDict<TClass> * SingletonInstance; ///< Singleton pointer.
        };
        /// Static member initialization
        template<class TClass> TClassIntegrandDict<TClass> * TClassIntegrandDict<TClass>::SingletonInstance =0;
    }
}
