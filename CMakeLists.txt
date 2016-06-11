cmake_minimum_required (VERSION 2.6)
project (DSF)

# TODO need to make Net platform agnostic
# add_subdirectory(net)
add_subdirectory(sim)
#add_subdirectory(vis)
add_subdirectory(util)

ADD_LIBRARY( DSF STATIC
  sim/integratorRK4.cpp
  sim/sim.cpp
#  util/math/mat3.cpp
#  util/math/vec3.cpp
#  util/tbl/tbl.cpp
#  util/tbl/tbl2d.cpp
#  util/xml/xml.cpp
  vis/MainWindow.cpp
  vis/render.cpp
)

TARGET_LINK_LIBRARIES(DSF sim vis util)

SET(CMAKE_C++_CREATE_STATIC_LIBRARY 1)
SET_TARGET_PROPERTIES(DSF PROPERTIES LINKER_LANGUAGE C)

# TODO clean up code to compile without -fpermissive
# note -std=gnu++11 isnt picking up (should get rid of the >> to > > errors)
#set(CMAKE_CXX_FLAGS "-fpermissive") # -set=c+++11 or something
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fpermissive")
#SET_TARGET_PROPERTIES(DSF PROPERTIES LINKER_LANGUAGE C)
