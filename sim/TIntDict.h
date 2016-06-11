#pragma once
	// find something more descriptive to name it ... 
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
		// Prototypes
		template<class base> class TClassBase;

			/// A dictionary of integrands for the integrator
		template <class TClass> class TClassIntegrandDict
		{
		public:
			/// Static method which retrieves the instance.
			/// If no instance is present, will istantiate one based on template data.
			static TClassIntegrandDict<TClass> * Instance()
			{
				if (SingletonInstance == NULL)
				{
					SingletonInstance = new TClassIntegrandDict<TClass>;
				}
				return SingletonInstance;
			};

			/// Add an entire vector of values and associated derivatives to the integrator.
			/// \param &v State vector.
			/// \param &dv Derivative vector.
			void add(TClassBase<TClass > *in, dsf::util::Vec3 &v, dsf::util::Vec3 &dv)
			{
				cout << "TClassIntegrandDict::add (vector)" << endl;
				for (int i=0; i<3; i++)
					addToIntegrator(in, v[i], dv[i]);
			}

			/// Add a matrix of values and associated derivatives to the integrator.
			/// \param &m State matrix.
			/// \param &dm Derivative matrix.
			void add(TClassBase<TClass > *in, dsf::util::Mat3 &m, dsf::util::Mat3 &dm)
			{
				cout << "TClassIntegrandDict::add (matrix)" << endl;
				for (int i=0; i<3; i++)
					for (int j=0; j<3; j++)
						addToIntegrator(in, m[i][j], dm[i][j]);
			}


			/// Add a state pair (value and derivative) to integrator.
			/// \param &x Value.
			/// \param &dx Derivative.
			void add(TClassBase<TClass > *in, double &x, double &dx)
			{
				cout << "TClassIntegrandDict::add (double)" << endl;
				addToIntegrator(in, x, dx);
			}

			/// Add a state pair (value and derivative) to integrator.
			/// \param &x Value.
			/// \param &dx Derivative.
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
				cout << "TClassIntegrandDict::constructor" << endl;
				xdd.resize(4);
			}
		public:
			std::vector<double*>x;											///< The state vector.
			std::vector<double>x0;											///< The initial condition of x, set at the beginning of an integration cycle.
			std::vector<double*>xd;											///< The derivative vector.
			std::vector< std::vector<double> >xdd;							///< Intermediate integration results.
			std::vector< TClassBase<TClass > >classDict;					///< The class corresponding to the integrand.
			static TClassIntegrandDict<TClass> * SingletonInstance;			///< Singleton Instance.
		};
			/// static member initialization for TClassIntegrandDict
		template<class TClass> TClassIntegrandDict<TClass> * TClassIntegrandDict<TClass>::SingletonInstance =0;
	}
}