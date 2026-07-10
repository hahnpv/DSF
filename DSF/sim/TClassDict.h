/**
 * @file TClassDict.h
 * @brief Template class factory and dictionary system.
 * 
 * Provides automatic factory registration for derived classes. Classes
 * register themselves at static initialization time using TClass<D,B>::Instance().
 */
#pragma once

#include <vector>
#include <iostream>
#include <string>
#include <map>
#include <set>
#include <boost/core/demangle.hpp>
#include "TIntDict.h"
using namespace std;

namespace dsf
{
    namespace sim 
    {
        // Forward declarations
        template<class base> class TClassBase;
        template<class derived, class base> class TClass;

        /**
         * @brief Metadata for a block property.
         */
        struct PropertyMetadata {
            string name;
            string type;
            string defaultValue;
            string description;
            size_t offset;
            /// "config" — read from the deck XML in configure(); the GUI may
            /// emit it as an attribute. "output" — runtime state published for
            /// introspection/telemetry/MC binding only; never written to a
            /// deck (a deck attribute with this name would go unread, which
            /// strict-mode validation treats as a typo).
            string direction = "config";
        };

        /**
         * @brief Metadata for a block port.
         */
        struct PortMetadata {
            string name;
            string type;
            string direction; // "input" or "output"
        };

        /**
         * @brief Global class-name → published-property-name index.
         *
         * Populated by TClassBase::AddProperty (i.e. by the DSF_PROPERTY /
         * DSF_PROPERTY_BIND macros) regardless of which TClassDict<Base>
         * dictionary the metadata was registered against — some classes
         * register their factory against Block but their metadata against a
         * domain base (SensorBase, EOMBase, ...), which lands in a different
         * dictionary. This flat index lets configure-time checks answer
         * "which attributes does class X publish?" from the concrete type
         * name alone (see warn_unknown_attributes() in block.h).
         *
         * Classes that never call AddProperty are absent; checks must treat
         * that as "not checkable" (no metadata does NOT mean no attributes).
         */
        inline std::map<std::string, std::set<std::string>>& PropertyNameRegistry()
        {
            static std::map<std::string, std::set<std::string>> registry;
            return registry;
        }

        /**
         * @brief Singleton dictionary of class factories.
         * 
         * Stores TClassBase pointers for all registered classes deriving from
         * a common base class. Enables runtime creation of objects by class name.
         * 
         * @tparam BClass Base class that all registered classes derive from.
         * 
         * ## Usage
         * @code{.cpp}
         * // Get existing singleton instance:
         * Block* b = TClassDict<Block>::Instance()->Get("MyModel", true);
         * @endcode
         */
        template <class BClass> class TClassDict
        {
        public:

            /**
             * @brief Get the singleton dictionary instance.
             * @return Pointer to the singleton TClassDict.
             */
            static TClassDict<BClass> * Instance()
            {
                if (SingletonInstance == NULL)
                {
                    SingletonInstance = new TClassDict<BClass>;
                }
                return SingletonInstance;
            };

            /**
             * @brief Add a class factory to the dictionary.
             * @param in TClassBase pointer to add.
             */
            void Add(TClassBase<BClass > *in)
            {
                classDictPtr.push_back( in);
            }

            /**
             * @brief Search for a class by name.
             * @param compareid Class name to search for.
             * @return Index in dictionary, or -1 if not found.
             */
            int search(std::string compareid)
            {
                for (unsigned int i=0; i<classDictPtr.size(); i++)
                {
                    if ( classDictPtr[i]->name().compare( compareid) == 0)
                        return i;
                }
                cout << " No match for id: " << compareid << " in dictionary " << boost::core::demangle( typeid(BClass).name() ) << endl;
                return -1;
            }

            /**
             * @brief Get class instance by template type.
             * @tparam RClass Derived class type to retrieve.
             * @return Pointer to class instance.
             */
            template<class RClass> RClass * Get(void)
            {
                std::string compareid = boost::core::demangle( typeid(RClass).name() );
                int ni = search( compareid);
                if ( ni >= 0)
                {
                    return (RClass *)classDictPtr[ni]->get();
                }
                 cout << " No match for id: " << compareid << " in dictionary " << boost::core::demangle( typeid(RClass).name() ) << endl;
                return 0;
            }

            /**
             * @brief Get class instance by name string.
             * @param id Class name to look up.
             * @param _new If true, create a new instance; if false, return singleton.
             * @return Pointer to class instance.
             */
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
                return 0;
            }

            std::vector<TClassBase<BClass > *>classDictPtr;     ///< Vector of class factories.
        private:
            static TClassDict<BClass> * SingletonInstance;      ///< Singleton instance pointer.
        };
        /// Static member initialization
        template<class BClass> TClassDict<BClass> * TClassDict<BClass>::SingletonInstance =0;


        /**
         * @brief Base class for type-erased class factories.
         * 
         * Stores metadata about a derived class type and provides virtual
         * methods to retrieve instances.
         * 
         * @tparam BClass Base class type.
         */
        template<class BClass> class TClassBase
        {
        public:
            virtual std::string name()   { return tDerived; };      ///< Get derived class name.
            virtual std::string base()   { return tBase; };         ///< Get base class name.
            virtual BClass * get()    { return obj; };              ///< Get singleton instance.
            virtual BClass * getnew() { cout << "TClassBase" << endl; return new BClass; }; ///< Create new instance.
            static  BClass * getStatic() { return (new BClass); };  ///< Static factory method.

            void AddProperty(string name, string type, string defaultValue, string description="",
                             size_t offset=0, string direction="config") {
                properties.push_back({name, type, defaultValue, description, offset, direction});
                // Only config-direction properties are legal deck attributes;
                // "output" properties are runtime state that configure() never
                // reads, so they must not whitelist a deck attribute.
                if (direction == "config")
                    PropertyNameRegistry()[tDerived].insert(name);
            }
            void AddPort(string name, string type, string direction) {
                ports.push_back({name, type, direction});
            }

            const std::vector<PropertyMetadata>& getProperties() const { return properties; }
            const std::vector<PortMetadata>& getPorts() const { return ports; }

        protected:
            std::string tBase;      ///< Base class type name.
            std::string tDerived;   ///< Derived class type name.
            BClass * obj;           ///< Singleton instance pointer.
            std::vector<PropertyMetadata> properties;
            std::vector<PortMetadata> ports;
        };

        /**
         * @brief Typed class factory for automatic registration.
         * 
         * Each derived class creates a static TClass instance to register itself
         * with the TClassDict at program startup.
         * 
         * @tparam DClass Derived class type.
         * @tparam BClass Base class type.
         * 
         * ## Usage
         * @code{.cpp}
         * // In .cpp file:
         * Block* MyModel::block = TClass<MyModel, Block>::Instance();
         * @endcode
         */
        template<class DClass, class BClass> class TClass : public TClassBase<BClass>
        {
        public:
            BClass * get()              { return   this->obj; };            ///< Get singleton instance.
            BClass * getnew()           { cout << "TClass" << endl; return new DClass; };       ///< Create new instance.
            static BClass * getStatic() { return (BClass*)(new DClass); };  ///< Static factory.

            /**
             * @brief Get/create the singleton TClass instance.
             * 
             * Calling this method registers the class with TClassDict.
             * @return Pointer to TClass singleton.
             */
            static TClass<DClass,BClass> * Instance()
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
                this->obj = new DClass;
            }
            static TClass<DClass,BClass> * SingletonInstance;   ///< Singleton instance.
        };
        /// Static member initialization
        template<class DClass, class BClass> TClass<DClass,BClass> * TClass<DClass,BClass>::SingletonInstance = 0;
    }
}
