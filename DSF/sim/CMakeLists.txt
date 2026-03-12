set(sim_source_files
  block.h
  integrator_base.h
  integratorRK4.h
  integratorRK4.cpp
  integrator_rk45.h
  integrator_rk45.cpp
  integrator_verlet.h
  integrator_verlet.cpp
  RTclock.h
  sim.h
  TIntDict.h
  TSkedDict.h
  clock.h
  output.h
  hdf5output.h
  log_level.h
  output.cpp
  event.h
  event.cpp
  sim.cpp
  TClassDict.h
  TRefDict.h
)
add_library(sim ${sim_source_files})
target_compile_options(sim PRIVATE -fpermissive)
set_target_properties(sim PROPERTIES POSITION_INDEPENDENT_CODE ON)
