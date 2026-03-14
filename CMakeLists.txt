cmake_minimum_required(VERSION 3.14)
project(DSF)

# Enforce Out-of-Source Builds
if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
    message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called build) and run CMake from there.")
endif()

# Set C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Find Dependencies
find_package(Boost 1.56 COMPONENTS program_options system serialization REQUIRED)
# find_package(pybind11 CONFIG REQUIRED)
include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG        v2.11.1
)
FetchContent_MakeAvailable(pybind11)

find_package(HDF5 COMPONENTS C CXX REQUIRED)
include_directories(${HDF5_INCLUDE_DIRS})

find_package(Doxygen)

# Default to Debug build if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Enable testing
enable_testing()

# Add Subdirectories
# External sixdof library integration
# External sixdof library integration
set(SIXDOF_SEARCH_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../sixdof")
if(NOT DEFINED SIXDOF_DIR AND EXISTS "${SIXDOF_SEARCH_PATH}")
    set(SIXDOF_DIR "${SIXDOF_SEARCH_PATH}")
    message(STATUS "Found sixdof at default location: ${SIXDOF_DIR}")
endif()

if(DEFINED SIXDOF_DIR)
    # We include headers but DO NOT add_subdirectory to avoid duplicate ABI build.
    include_directories("${SIXDOF_DIR}")
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
    DSF/util/math/mat4.cpp
    DSF/util/math/quat.cpp
    DSF/util/math/vec3.cpp
    DSF/util/tbl/tbl.cpp
    DSF/util/tbl/tablend.cpp
    DSF/util/tbl/tbl2d.cpp
)


# Target Properties
target_include_directories(DSF PUBLIC 
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
    ${Boost_INCLUDE_DIRS}
)

target_link_libraries(DSF PUBLIC sim net util ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_compile_options(DSF PRIVATE -fpermissive)
set_target_properties(DSF PROPERTIES LINKER_LANGUAGE CXX)

# Python Bindings Module
pybind11_add_module(dsf_core 
    python/bindings/bindings_main.cpp
    python/bindings/bindings_util.cpp
    python/bindings/bindings_sim.cpp
    python/bindings/bindings_net.cpp
)
target_link_libraries(dsf_core PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
 target_include_directories(dsf_core PRIVATE 
    ${Boost_INCLUDE_DIRS}
)
target_compile_options(dsf_core PRIVATE -fpermissive)

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

# --- Python Tests (CTest Integration) ---
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# Determine paths for PYTHONPATH
# We want: <source_dir>/python (for the package)
# And: <binary_dir> (for dsf_core.so)
set(PYTHON_TEST_PATH "${CMAKE_SOURCE_DIR}/python")
set(BINARY_TEST_PATH "${CMAKE_BINARY_DIR}")

add_test(NAME python_tests
         COMMAND ${Python3_EXECUTABLE} -m pytest python/tests
         WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

# Set environment for the test execution
# Combine source and binary paths for PYTHONPATH
set_tests_properties(python_tests PROPERTIES ENVIRONMENT 
    "PYTHONPATH=${PYTHON_TEST_PATH}:${BINARY_TEST_PATH}:$ENV{PYTHONPATH}"
)

# On Linux, help the dynamic linker find the libraries we just built
if(UNIX)
    set(TEST_LIB_PATH "${BINARY_TEST_PATH}:$ENV{LD_LIBRARY_PATH}")
    set_property(TEST python_tests APPEND PROPERTY ENVIRONMENT "LD_LIBRARY_PATH=${TEST_LIB_PATH}")
endif()
