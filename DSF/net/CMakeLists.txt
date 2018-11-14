set(net_source_files
  data.h
  msg.h
  net.cpp
  net.h
  netmon.cpp
  netmon.h
  to_string.h
  WindowsSockets.h
)
add_library(net ${net_source_files})

SET_TARGET_PROPERTIES(net PROPERTIES LINKER_LANGUAGE C)
