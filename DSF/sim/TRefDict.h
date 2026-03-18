/**
 * @file TRefDict.h
 * @brief Template reference functions for retrieving block instances.
 * 
 * Provides convenience functions for looking up blocks by ID string,
 * supporting both factory singletons and runtime simulation graph traversal.
 */
#pragma once

#include <vector>
#include <typeinfo>
#include <exception>
#include <iostream>
#include <string>
#include "../util/demangle.h"
#include "TClassDict.h"

using namespace std;

namespace dsf
{
    namespace sim 
    {
        /**
         * @brief Get singleton instance from TClassDict by ID.
         * 
         * Looks up a class factory by name and returns the singleton instance.
         * 
         * @tparam BClass Base class type of the dictionary.
         * @param id Class name to look up.
         * @return Pointer to singleton instance, or nullptr if not found.
         * 
         * ## Usage
         * @code{.cpp}
         * EOMBase* eom = TRef<EOMBase>("OblateEarth");
         * @endcode
         */
        template<class BClass> BClass * TRef(std::string id)
        {
            return TClassDict<BClass>::Instance()->Get( id, false);
        }

        /**
         * @brief Get singleton instance with static cast to derived type.
         * 
         * @tparam BClass Base class type of the dictionary.
         * @tparam DClass Derived class type to cast to.
         * @param id Class name to look up.
         * @return Pointer cast to DClass type.
         */
        template<class BClass, class DClass> DClass* TRefCast(std::string id)
        {
            return static_cast<DClass*>( TRef<BClass>( id) );
        }

        /**
         * @brief Create a new instance from TClassDict by ID.
         * 
         * Unlike TRef, this creates a unique new instance each time called.
         * 
         * @tparam BClass Base class type of the dictionary.
         * @param id Class name to look up.
         * @return Pointer to new instance.
         */
        template<class BClass> BClass* TRefUnique(std::string id)
        {
            return TClassDict<BClass>::Instance()->Get( id, true);
        }

        /**
         * @brief Recursively search simulation graph for a block by class ID.
         * 
         * Starting from block b, searches children then traverses up the parent
         * chain until a matching block is found.
         * 
         * @tparam BClass Base class type (typically Block).
         * @tparam DClass Derived class type to find and return.
         * @param b Starting block for search.
         * @param id Class name to search for.
         * @return Pointer to found block cast to DClass, or nullptr.
         * 
         * ## Usage
         * @code{.cpp}
         * RocketProp* prop = TRefSim<Block, RocketProp>(this, "RocketProp");
         * @endcode
         */
        template<class BClass, class DClass> DClass * TRefSim(BClass * b, std::string id)
        {
            // Pass 1: match by class name (original behavior — backward compatible)
            for ( unsigned int i = 0; i < b->getChildren().size(); i++)
            {
                std::string classid   = dsf::util::demangle( typeid(*(b->getChild(i))).name() );
                std::string compareid = id;
                if ( classid.compare(compareid) == 0)
                {
                    return dynamic_cast<DClass*>( b->getChild(i));
                }
            }

            // Pass 2: match by instance name (XML "id" attribute) with type check
            // This handles cases where id != class name, e.g.
            //   <aero id="CapsuleAero" class="ReentryAero" />
            for ( unsigned int i = 0; i < b->getChildren().size(); i++)
            {
                if ( b->getChild(i)->getName() == id )
                {
                    DClass* result = dynamic_cast<DClass*>( b->getChild(i) );
                    if (result) return result;
                }
            }

            if ( b->getParent() == 0)
            {
                cout << "TRefSim<" << dsf::util::demangle( typeid(BClass).name() ) << ", " << dsf::util::demangle( typeid(DClass).name() ) << ">( " << id << "):" << endl;
                cout << "\tNo match found in sim." << endl;
                return 0;
            }

            return TRefSim<BClass, DClass>(b->getParent(), id);
        }

        /**
         * @brief Search simulation graph for a block by its instance name (id attribute).
         * 
         * Unlike TRefSim which searches by class type, this function searches
         * by the block's getName() value (the 'id' attribute from XML).
         * 
         * @tparam DClass Derived class type to find and return.
         * @param parent Starting block for search (typically the block's parent).
         * @param name Instance name to search for.
         * @return Pointer to found block cast to DClass, or nullptr if not found.
         * 
         * ## Usage
         * @code{.cpp}
         * GroundStation* station = TRefSimByName<GroundStation>(parent, "Anchor");
         * @endcode
         */
        template<typename DClass>
        DClass* TRefSimByName(Block* parent, const std::string& name) {
            if (!parent) return nullptr;
            for (Block* child : parent->getChildren()) {
                if (child->getName() == name) {
                    return dynamic_cast<DClass*>(child);
                }
            }
            return nullptr;
        }
    }
}
