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
  hdf5output.h
  log_level.h
  output.cpp
  sim.cpp
  TClassDict.h
  TRefDict.h
)
add_library(sim ${sim_source_files})
target_compile_options(sim PRIVATE -fpermissive)
