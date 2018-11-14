cmake_minimum_required (VERSION 2.6)
project (DSF)

FIND_PACKAGE( Boost 1.50 )
INCLUDE_DIRECTORIES( ${Boost_INCLUDE_DIR} )
INCLUDE_DIRECTORIES(DSF)

# TODO need to make Net platform agnostic
# add_subdirectory(DSV/net)
add_subdirectory(DSF/sim)
#add_subdirectory(DSF/vis)
add_subdirectory(DSF/util)
add_subdirectory(examples/sixdof)

ADD_LIBRARY( DSF STATIC
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


ADD_EXECUTABLE(sixdof examples/sixdof/main.cpp)

#TARGET_LINK_LIBRARIES(DSF sim vis util)
TARGET_LINK_LIBRARIES(DSF sim util ${Boost_LIBRARIES} )
TARGET_LINK_LIBRARIES(sixdof DSF  ${Boost_LIBRARIES} )

SET(CMAKE_C++_CREATE_STATIC_LIBRARY 1)
SET_TARGET_PROPERTIES(DSF PROPERTIES LINKER_LANGUAGE C)

# TODO clean up code to compile without -fpermissive
# note -std=gnu++11 isnt picking up (should get rid of the >> to > > errors)
#set(CMAKE_CXX_FLAGS "-fpermissive") # -set=c+++11 or something
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fpermissive")
#SET_TARGET_PROPERTIES(DSF PROPERTIES LINKER_LANGUAGE C)
