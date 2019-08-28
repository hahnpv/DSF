set(net_source_files
  data.h
  msg.h
  NetClient.cpp
  NetClient.h
  NetServer.cpp
  NetServer.h
)

add_library(net ${net_source_files})
SET_TARGET_PROPERTIES(net PROPERTIES LINKER_LANGUAGE C)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fpermissive")
