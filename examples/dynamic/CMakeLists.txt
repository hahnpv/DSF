set(sixdof_dynamic_files
 main.cpp
)
ADD_EXECUTABLE(dynamicsixdof ${sixdof_dynamic_files})
SET_TARGET_PROPERTIES(dynamicsixdof PROPERTIES LINKER_LANGUAGE C)
TARGET_LINK_LIBRARIES(dynamicsixdof DSF dl ${Boost_LIBRARIES})
set(CMAKE_CXX_FLAGS "-fpermissive")
CONFIGURE_FILE(../sixdof/satellite.xml satellite.xml COPYONLY)
CONFIGURE_FILE(../sixdof/vehicle.xml vehicle.xml COPYONLY)
CONFIGURE_FILE(../sixdof/config/6dofTables.dat config/6dofTables.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/6dofMortar3.dat config/6dofMortar3.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/pwt-0.005.dat config/pwt-0.005.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/pwt-0.015.dat config/pwt-0.015.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/pwt-0.025.dat config/pwt-0.025.dat COPYONLY)
CONFIGURE_FILE(../sixdof/config/6dofSquibPack.dat config/6dofSquibPack.dat COPYONLY)

