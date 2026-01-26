cmake_minimum_required(VERSION 3.14)
project(DSF)

# Enforce Out-of-Source Builds
if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
    message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called build) and run CMake from there.")
endif()

# Set C++ Standard
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Find Dependencies
find_package(Boost 1.56 COMPONENTS program_options system serialization REQUIRED)
find_package(OpenSceneGraph 2.0.0 REQUIRED osgDB osgUtil)
find_package(Doxygen)

# Default to Debug build if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

# Add Subdirectories
# External sixdof library integration
set(SIXDOF_SEARCH_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../sixdof")
if(NOT DEFINED SIXDOF_DIR AND EXISTS "${SIXDOF_SEARCH_PATH}")
    set(SIXDOF_DIR "${SIXDOF_SEARCH_PATH}")
    message(STATUS "Found sixdof at default location: ${SIXDOF_DIR}")
endif()

if(DEFINED SIXDOF_DIR)
    if(EXISTS "${SIXDOF_DIR}/sixdof/CMakeLists.txt")
        add_subdirectory("${SIXDOF_DIR}/sixdof" "${CMAKE_BINARY_DIR}/sixdof_build")
    else()
        message(WARNING "SIXDOF_DIR is set to ${SIXDOF_DIR} but ${SIXDOF_DIR}/sixdof/CMakeLists.txt not found.")
    endif()
else()
    message(STATUS "sixdof library not found (checked ../sixdof). Skipping.")
endif()

add_subdirectory(DSF/sim)
add_subdirectory(DSF/net)
add_subdirectory(DSF/util)

# Create Main Library
add_library(DSF SHARED
    DSF/sim/integratorRK4.cpp
    DSF/sim/sim.cpp
    DSF/net/NetClient.cpp
    DSF/net/NetServer.cpp
    DSF/util/math/mat3.cpp
    DSF/util/math/vec3.cpp
    DSF/util/tbl/tbl.cpp
    DSF/util/tbl/tbl2d.cpp
    DSF/util/xml/xml.cpp
)

# Target Properties
target_include_directories(DSF PUBLIC 
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
    ${Boost_INCLUDE_DIRS}
    ${OPENSCENEGRAPH_INCLUDE_DIRS}
)

target_link_libraries(DSF PUBLIC sim net util ${Boost_LIBRARIES})
target_compile_options(DSF PRIVATE -fpermissive)
set_target_properties(DSF PROPERTIES LINKER_LANGUAGE CXX)

# Add Examples
add_subdirectory(examples/dynamic)
add_subdirectory(examples/bouncy)



# Documentation
if(DOXYGEN_FOUND)
    set(DOXYGEN_INPUT Doxyfile.in)
    set(DOXYGEN_OUTPUT Doxyfile)
    add_custom_command(
        OUTPUT ${DOXYGEN_OUTPUT}
        COMMAND ${CMAKE_COMMAND} -E echo_append "Building API Documentation..."
        COMMAND ${DOXYGEN_EXECUTABLE} ${DOXYGEN_INPUT}
        COMMAND ${CMAKE_COMMAND} -E echo "Done."
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        DEPENDS ${DOXYGEN_INPUT}
    )
    add_custom_target(doc ALL DEPENDS ${DOXYGEN_OUTPUT})
endif()
