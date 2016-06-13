#pragma once
	// find something more descriptive to name it ... 
#include <vector>
#include <typeinfo>
#include <exception>
#include <iostream>
#include <string>
#include <boost/core/demangle.hpp>

#include "TClassDict.h"

using namespace std;

	// note to self: use of TClass as template param in TClassDict and 
	// as name of template class is confusing, pick one and rename the other
namespace dsf
{
	namespace sim 
	{
		/// Version for use with XML : returns calling class as a template argument
		/// Useless at the moment as it requires RClass to be specified and we'd rather grab child classes of unknown RClass
		/// \param BClass base class of TClass (ie: dictionary type)
		/// \param RClass reference type
/*		template<class BClass, class RClass> RClass * TRef ()
		{
			return TClassDict<BClass>::Instance()->Get<RClass>();					// if we add int param to get, can implement it here
		}																			// with a default of =0;
*/	
		/// Returns a pointer to class obj held by TClassDict by searching ID
		template<class BClass> BClass * TRef(std::string id)
		{
			return TClassDict<BClass>::Instance()->Get("class " + id, false);
		}

		/// Returns a pointer to class obj held by TClassDict by searching ID, typecast to RClass
		template<class BClass, class DClass> DClass* TRefCast(std::string id)
		{
			return static_cast<DClass*>( TRef<BClass>( id) );				// cast as derived class
		}

		/// Returns a pointer to a unique object by searching ID
		template<class BClass> BClass* TRefUnique(std::string id)
		{
//2016 - is this MSVC kludge?			return TClassDict<BClass>::Instance()->Get("class " + id, true);return TClassDict<BClass>::Instance()->Get("class " + id, true);
			return TClassDict<BClass>::Instance()->Get(id, true);
		}

		/// Recursively traverses block tree, starting at leaf node, going up until it finds BClass by ID
		template<class BClass, class DClass> DClass * TRefSim(BClass * b, std::string id)
		{
			for ( unsigned int i = 0; i < b->getChildren().size(); i++)
			{
				std::string classid   = boost::core::demangle( typeid(*(b->getChild(i))).name() );
				// std::string compareid = "class " + id;
				std::string compareid = id;
				if ( classid.compare(compareid) == 0)
				{
					return dynamic_cast<DClass*>( b->getChild(i));
				}
			}

			if ( b->getParent() == 0)
			{
				cout << "TRefSim<" << boost::core::demangle( typeid(BClass).name() ) << ", " << boost::core::demangle( typeid(DClass).name() ) << ">( " << id << "):" << endl;
				cout << "\tNo match found in sim." << endl;
				cin.get();
				return 0;
			}

			TRefSim<BClass, DClass>(b->getParent(), id);
			// Ignore warning. Placing a dummy retval causes the retval from TRefSim to get overwritten as it recurses back.
		}
	}
}