set(sixdof_source_files
 AeroBase.cpp
 AtmosBase.cpp
 atmosphere.cpp
 EarthBase.cpp
 FlatEarth.cpp
 linear.cpp
 main.cpp 
 MassBase.cpp 
 mass.cpp
 MissileAero.cpp
 MissileFin.cpp
 OblateEarth.cpp
 PropBase.cpp
 ReentryAero.cpp
 RocketProp.cpp
 scriptedtarget.cpp
 simpleguidance.cpp
 squib.cpp
 stage_mass.cpp
 vehicle.cpp
 wgs84.cpp
)
add_library(sixdofsrc ${sixdof_source_files})
SET_TARGET_PROPERTIES(sixdofsrc PROPERTIES LINKER_LANGUAGE C)
set(CMAKE_CXX_FLAGS "-fpermissive")
