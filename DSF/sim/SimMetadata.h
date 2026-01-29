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

#define DSF_PROPERTY(propName, type, defaultValue, description) \
    static inline bool _reg_prop_##propName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddProperty(#propName, type, defaultValue, description); \
        return true; \
    }();

#define DSF_PORT(portName, type, direction) \
    static inline bool _reg_port_##portName = []() { \
        dsf::sim::TClass<_ThisClass, _BaseClass>::Instance()->AddPort(#portName, type, direction); \
        return true; \
    }();
