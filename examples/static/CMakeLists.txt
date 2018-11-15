set(sixdof_static_files
 ../sixdof/AeroBase.cpp
 ../sixdof/AtmosBase.cpp
 ../sixdof/atmosphere.cpp
 ../sixdof/EarthBase.cpp
 ../sixdof/FlatEarth.cpp
 ../sixdof/linear.cpp
 ../sixdof/MassBase.cpp
 main.cpp
 ../sixdof/mass.cpp
 ../sixdof/MissileAero.cpp
 ../sixdof/MissileFin.cpp
 ../sixdof/OblateEarth.cpp
 ../sixdof/PropBase.cpp
 ../sixdof/ReentryAero.cpp
 ../sixdof/RocketProp.cpp
 ../sixdof/scriptedtarget.cpp
 ../sixdof/simpleguidance.cpp
 ../sixdof/squib.cpp
 ../sixdof/stage_mass.cpp
 ../sixdof/vehicle.cpp
 ../sixdof/wgs84.cpp
)
ADD_EXECUTABLE(staticsixdof ${sixdof_static_files})
SET_TARGET_PROPERTIES(staticsixdof PROPERTIES LINKER_LANGUAGE C)
TARGET_LINK_LIBRARIES(staticsixdof DSF ${Boost_LIBRARIES})
set(CMAKE_CXX_FLAGS "-fpermissive")
CONFIGURE_FILE(../sixdof/satellite.xml satellite.xml COPYONLY)
CONFIGURE_FILE(../sixdof/vehicle.xml vehicle.xml COPYONLY)
CONFIGURE_FILE(../sixdof/config/6dofTables.dat config/6dofTables.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/6dofMortar3.dat config/6dofMortar3.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/pwt-0.005.dat config/pwt-0.005.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/pwt-0.015.dat config/pwt-0.015.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/pwt-0.025.dat config/pwt-0.025.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/6dofSquibPack.dat config/6dofSquibPack.dat COPYONLY)
