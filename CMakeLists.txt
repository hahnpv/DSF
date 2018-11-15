cmake_minimum_required (VERSION 2.6)
project (DSF)

FIND_PACKAGE( Boost 1.50 COMPONENTS program_options REQUIRED)

INCLUDE_DIRECTORIES( ${Boost_INCLUDE_DIR} )
INCLUDE_DIRECTORIES(DSF)

#SET(CMAKE_BUILD_TYPE RelWithDebInfo) # release build with debug symbols
SET(CMAKE_BUILD_TYPE Debug)

# TODO need to make Net platform agnostic
add_subdirectory(DSF/sim)
#add_subdirectory(DSV/net)
#add_subdirectory(DSF/vis)
add_subdirectory(DSF/util)

# Add examples
add_subdirectory(examples/sixdof)		# 6DOF Library (shared object)
add_subdirectory(examples/static)		# Staticly compiled 6DOF executable
add_subdirectory(examples/dynamic)		# Dynamic DSF executable (loads any shared object library)

# Create DSF library
ADD_LIBRARY( DSF SHARED
  DSF/sim/integratorRK4.cpp
  DSF/sim/sim.cpp
  DSF/util/math/mat3.cpp
  DSF/util/math/vec3.cpp
  DSF/util/tbl/tbl.cpp
  DSF/util/tbl/tbl2d.cpp
  DSF/util/xml/xml.cpp
#  DSF/vis/MainWindow.cpp
#  DSF/vis/render.cpp
)


TARGET_LINK_LIBRARIES(DSF sim util ${Boost_LIBRARIES} )
SET(CMAKE_C++_CREATE_STATIC_LIBRARY 1)
SET_TARGET_PROPERTIES(DSF PROPERTIES LINKER_LANGUAGE C)

# TODO clean up code to compile without -fpermissive
# note -std=gnu++11 isnt picking up (should get rid of the >> to > > errors)
#set(CMAKE_CXX_FLAGS "-fpermissive") # -set=c+++11 or something
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fpermissive")
#SET_TARGET_PROPERTIES(DSF PROPERTIES LINKER_LANGUAGE C)


# Generate documentation
FIND_PACKAGE(Doxygen)
IF (DOXYGEN_FOUND)
SET(DOXYGEN_INPUT Doxyfile.in)
SET(DOXYGEN_OUTPUT Doxyfile)

ADD_CUSTOM_COMMAND(
  OUTPUT ${DOXYGEN_OUTPUT}
  COMMAND ${CMAKE_COMMAND} -E echo_append "Building API Documentation..."
  COMMAND ${DOXYGEN_EXECUTABLE} ${DOXYGEN_INPUT}
  COMMAND ${CMAKE_COMMAND} -E echo "Done."
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  DEPENDS ${DOXYGEN_INPUT}
  )

ADD_CUSTOM_TARGET(doc ALL DEPENDS ${DOXYGEN_OUTPUT})
ENDIF (DOXYGEN_FOUND)
