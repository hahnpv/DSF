#pragma once
	// find something more descriptive to name it ... 
#include <vector>
#include <typeinfo>
#include <exception>
#include <iostream>
#include <string>

#include "TIntDict.h"		// temporary, eventually make derived classes include as needed
using namespace std;

	// scheduler
	// work on later
namespace dsf
{
	namespace sim 
	{
		// Prototypes
		template<class base> class TClassBase;

			/// A scheduler
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
