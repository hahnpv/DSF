/**
 * @file TSkedDict.h
 * @brief Placeholder scheduler dictionary (future use).
 *
 * Intended as a scheduler for ordered block execution, analogous to
 * how TClassDict manages the factory dictionary.  Currently a stub.
 */
#pragma once

#include <vector>
#include <typeinfo>
#include <exception>
#include <iostream>
#include <string>

#include "TIntDict.h"
using namespace std;

namespace dsf
{
	namespace sim 
	{
		template<class base> class TClassBase;

		/**
		 * @brief Scheduler dictionary (stub — not yet implemented).
		 * @tparam TClass Base class type.
		 */
		template <class TClass> class TSkedDict
		{
		public:

			/// Static method which retrieves the instance.
			/// If no instance is present, will istantiate one based on template data.
			static TSkedDict<TClass> * Instance()
			{
				if (SingletonInstance == NULL)
				{
					SingletonInstance = new TSkedDict<TClass>;
				}
				return SingletonInstance;
			};

			/// tricky part is derived class is going to have to store the fpt
			void Add(TClassBase<TClass > *in)
			{
			}


			// temporarily public for TClassRefDict
			std::vector<TClassBase<TClass > >classDict;				///< Class Dictionary
		private:
			static TSkedDict<TClass> * SingletonInstance;			///< Singleton Instance
		};
			/// static member initialization for TClassDict
		template<class TClass> TSkedDict<TClass> * TSkedDict<TClass>::SingletonInstance =0;
	}
}
