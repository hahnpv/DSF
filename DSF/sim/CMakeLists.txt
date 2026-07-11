set(sim_source_files
  block.h
  integrator_base.h
  integratorRK4.h
  integratorRK4.cpp
  integrator_rk45.h
  integrator_rk45.cpp
  integrator_verlet.h
  integrator_verlet.cpp
  sim.h
  TIntDict.h
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
# OBJECT library: compiled once, aggregated into libDSF.so by the
# top-level CMakeLists (no second compilation, no separate archive).
add_library(sim OBJECT ${sim_source_files})
set_target_properties(sim PROPERTIES POSITION_INDEPENDENT_CODE ON)
