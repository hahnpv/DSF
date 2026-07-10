/**
 * @file SimMetadata.h
 * @brief Macros for decorating DSF blocks with metadata.
 * 
 * These macros allow blocks to publish their properties and ports
 * to the simulation factory, enabling automatic GUI introspection.
 */
#pragma once

#include "TClassDict.h"

#define DSF_METADATA_START(CLASS, BASE) \
    typedef CLASS _ThisClass; \
    typedef BASE _BaseClass;

// Configuration properties — read from the deck XML in configure(). These are
// what the GUI inspector offers for editing and what the .dsf → XML converter
// may emit as attributes.
#define DSF_PROPERTY(propName, type, defaultValue, description) \
    static inline bool _reg_prop_##propName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddProperty(#propName, type, defaultValue, description, 0, "config"); \
        return true; \
    }();

#define DSF_PROPERTY_BIND(propName, memberName, type, defaultValue, description) \
    static inline bool _reg_prop_##propName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddProperty(#propName, type, defaultValue, description, offsetof(_ThisClass, memberName), "config"); \
        return true; \
    }();

// Output/state properties — runtime values published for introspection,
// live probing, and Monte-Carlo binding, but NOT read from the deck. The GUI
// must not emit them as deck attributes: configure() never reads them, so
// strict-mode validation would (correctly) flag them as unused.
#define DSF_OUTPUT(propName, type, defaultValue, description) \
    static inline bool _reg_prop_##propName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddProperty(#propName, type, defaultValue, description, 0, "output"); \
        return true; \
    }();

#define DSF_OUTPUT_BIND(propName, memberName, type, defaultValue, description) \
    static inline bool _reg_prop_##propName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddProperty(#propName, type, defaultValue, description, offsetof(_ThisClass, memberName), "output"); \
        return true; \
    }();

#define DSF_PORT(portName, type, direction) \
    static inline bool _reg_port_##portName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddPort(#portName, type, direction); \
        return true; \
    }();
