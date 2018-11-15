set(sixdof_dynamic_files
 main.cpp
)
ADD_EXECUTABLE(dynamicsixdof ${sixdof_dynamic_files})
SET_TARGET_PROPERTIES(dynamicsixdof PROPERTIES LINKER_LANGUAGE C)
TARGET_LINK_LIBRARIES(dynamicsixdof DSF dl ${Boost_LIBRARIES})
set(CMAKE_CXX_FLAGS "-fpermissive")
CONFIGURE_FILE(../sixdof/satellite.xml satellite.xml COPYONLY)

