#pragma once

#include <vector>
#include <iostream>
#include <string>
#include <boost/core/demangle.hpp>

#include "TIntDict.h"		// temporary, eventually make derived classes include as needed
using namespace std;

namespace dsf
{
	namespace sim 
	{
		// Prototypes
		template<class base> class TClassBase;
		template<class derived, class base> class TClass;

			/// A dictionary of classes deriving off of a common parent.
			/// \param TClass The class on which the dictionary is based. NO RELATION TO TCLASS<T> ... rename
		template <class BClass> class TClassDict
		{
		public:

			/// Static method which retrieves the instance.
			/// If no instance is present, will istantiate one based on template data.
			static TClassDict<BClass> * Instance()
			{
				if (SingletonInstance == NULL)
				{
					SingletonInstance = new TClassDict<BClass>;
				}
				return SingletonInstance;
			};

			/// Method to add classes to the dictionary
			/// \param *in TClass<DClass,BClass> to add to the dictionary.
			void Add(TClassBase<BClass > *in)
			{
				classDictPtr.push_back( in);
			}

			int search(std::string compareid)
			{
				cout << " there are "  << classDictPtr.size() << " elements" << endl;
				for (unsigned int i=0; i<classDictPtr.size(); i++)
				{
					cout << "\t" << classDictPtr[i]->name() << " of base" << classDictPtr->base() << endl;
					if ( classDictPtr[i]->name().compare( compareid) == 0)
						return i;
				}
				cout << " No match for id: " << compareid << " in dictionary " << boost::core::demangle( typeid(BClass).name() ) << endl;
				return -1;
			}

			template<class RClass> RClass * Get(void)				///< Returns the class in dictionary corresponding to RClass
			{
				std::string compareid = boost::core::demangle( typeid(RClass).name() );
				int ni = search( compareid);
				if ( ni >= 0)
				{
					cout << "match " << boost::core::demangle( typeid(RClass).name() ) << "  " << classDictPtr[ni].name() << endl;
					return (RClass *)classDictPtr[ni]->get();
				}

				return 0;											/// null pointer
			}

			BClass * Get(std::string id, bool _new)
			{
				int ni = search( id);
				if ( ni >= 0)
				{
					if ( _new)
						return (classDictPtr[ni]->getnew());
					else 
						return classDictPtr[ni]->get();
				}

				return 0;											/// null pointer
			}

			// temporarily public for TClassRefDict
			std::vector<TClassBase<BClass > *>classDictPtr;			///< Class Dictionary
		private:
			static TClassDict<BClass> * SingletonInstance;			///< Singleton Instance
		};
			/// static member initialization for TClassDict
		template<class BClass> TClassDict<BClass> * TClassDict<BClass>::SingletonInstance =0;


		/// TClassBase holds the base class, B, of derivative class DClass.
		/// TClass inherits TClassBase an stores DClass.
		/// This inheritance allows TClasses containing varied classes to 
		/// exist in the same dictionary if they share base class B
		template<class BClass> class TClassBase
		{
		public:
			virtual std::string name()   { return tDerived; };						///< Return the name of the derived class.
			virtual std::string base()   { return tBase; };							///< Return the name of the base class.
			virtual BClass * get()    	 { return obj; };						///< Returns singleton instance 
			virtual BClass * getnew() 	 { cout << "TClassBase" << endl; return new BClass; };				///< Get a unique copy
			static  BClass * getStatic() { return (new BClass); };	///< Get a new static copy (to get into dict) [TODO NOTE: removed static from return arg due to compiler error]
		protected:
			std::string tBase;												///< base class inheritance name.
			std::string tDerived;											///< derived class inheritance name.
			BClass * obj;													///< class object.
		};

		/// TClass inherits TClassBase. TClass stores derivative class DClass derived from class BClass. 
		/// All classes sharing the same TClassBase will get stored in the same TClassDict
		/// \param DClass Derived class name.
		/// \param BClass Base class name.
		template<class DClass, class BClass> class TClass : public TClassBase<BClass>
		{
		public:
			BClass * get()			    { return   this->obj; };							///< Get ptr to obj; not unique DClass
			BClass * getnew()		    {  cout << "TClass" << endl; return new DClass; };						///< Get a unique DClass object ptr
			static BClass * getStatic() { return (BClass*)((new DClass)); };	///< Get a new static copy (to get into dict) [TODO NOTE: removed static from return arg due to compiler error]

			static TClass<DClass,BClass> * Instance()							///< Create an instance, and add to the TClassDict
			{
				if (SingletonInstance == NULL)
				{
					SingletonInstance = new TClass<DClass,BClass>;
					TClassDict<BClass>::Instance()->Add(SingletonInstance);
				}
				return SingletonInstance;
			}
		private:
			TClass<DClass, BClass>()
			{
				this->tBase    = boost::core::demangle( typeid(BClass).name() );
				this->tDerived = boost::core::demangle( typeid(DClass).name() );
				this->obj = new DClass;							// calls constructor, which calls the integrator template, recursion.
			}
			static TClass<DClass,BClass> * SingletonInstance;						///< Singleton Instance of this
		};
			/// static member initialization for TClassIntegrandDict
		template<class DClass, class BClass> TClass<DClass,BClass> * TClass<DClass,BClass>::SingletonInstance = 0;


			/// getStatic returns a static copy of the deriv object for addition to the dictionary
			/// "Return type is necessary for the 'syntactic sugar' to work. In order for this dictionary
			/// to work automatically out of the box before invoking any classes, we need to initialize a
			/// static member in each class. Each of those static members will get initialized before the
			/// program proceeds. Well, to instantiate them, call this function with the appropriate template
			/// parameters (IE, if your class is b, derived from a, TClass<b,a>::Instance() to set the value of
			/// the static variable in your program. If you tried calling this outside of your class definition
			/// without having it be the assignment of that static variable, the compiler would return an error 
			/// stating that you were attempting to re-define the function as it exists here"


	}
}
