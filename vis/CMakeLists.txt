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
)
add_library(vis ${vis_source_files})

SET_TARGET_PROPERTIES(vis PROPERTIES LINKER_LANGUAGE C)
