set(net_source_files
  data.h
  msg.h
  NetClient.cpp
  NetClient.h
  NetServer.cpp
  NetServer.h
)

add_library(net ${net_source_files})
target_compile_options(net PRIVATE -fpermissive)
if(DEFINED SIXDOF_DIR)
    target_include_directories(net PUBLIC "${SIXDOF_DIR}")
endif()
target_include_directories(net PUBLIC "${CMAKE_SOURCE_DIR}/DSF")
