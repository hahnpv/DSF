set(sim_source_files
  block.h
  integratorRK4.h
  RTclock.h
  sim.h
  TIntDict.h
  TSkedDict.h
  clock.h
  integratorRK4.cpp
  output.h
  sim.cpp
  TClassDict.h
  TRefDict.h
)
add_library(sim ${sim_source_files})

SET_TARGET_PROPERTIES(sim PROPERTIES LINKER_LANGUAGE C)
set(CMAKE_CXX_FLAGS "-fpermissive")
