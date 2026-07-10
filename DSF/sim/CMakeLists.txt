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
  phase_sequencer.h
  sim.cpp
  TClassDict.h
  TRefDict.h
)
add_library(sim ${sim_source_files})
set_target_properties(sim PROPERTIES POSITION_INDEPENDENT_CODE ON)
