set(vis_source_files
  baseCallback.h
  findCallbackNode.h
  MainWindow.h
  orbitCamera.h
  scene.h
  xmlinput.h
  cameraBase.h
  findNode.h
  monitor.h
  render.cpp
  staticCamera.h
  MainWindow.cpp
  netCallback.h
  render.h
  tblCallback.h
  main.cpp
)


set(sixdof_dynamic_files
 main.cpp
)

ADD_EXECUTABLE(vis ${vis_source_files})
SET_TARGET_PROPERTIES(vis PROPERTIES LINKER_LANGUAGE C)
TARGET_INCLUDE_DIRECTORIES(vis PRIVATE /usr/include/fox-1.6)
TARGET_LINK_LIBRARIES(vis DSF dl ${Boost_LIBRARIES} ${OPENSCENEGRAPH_LIBRARIES} -L/usr/lib/x86_64-linux-gnu/ -lFOX-1.6)

set(CMAKE_CXX_FLAGS "-fpermissive")

CONFIGURE_FILE(bullet.osg bullet.osg COPYONLY)
CONFIGURE_FILE(wgs84sphere.osg wgs84sphere.osg COPYONLY)
CONFIGURE_FILE(visualize40s.csv visualize40s.csv COPYONLY)
CONFIGURE_FILE(vehicle.xml vehicle.xml COPYONLY)
