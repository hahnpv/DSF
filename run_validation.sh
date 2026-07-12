#!/bin/bash
# Compile the test harness
g++ -o verify_atmos ../sixdof/validation/verify_atmos_1976.cpp \
    -I../sixdof \
    -I../DSF/DSF \
    -I../DSF \
    -L./build/sixdof_build \
    -lsixdof \
    -Wl,-rpath,./build/sixdof_build \
    -std=c++17

# Run it
./verify_atmos

# Compile and run Fortran Reference
gfortran -o run_fortran ../sixdof/tmp/atmos76.f90 ../sixdof/tmp/run_atmos_fortran.f90
./run_fortran
mv atmos_fortran_output.csv ../sixdof/tmp/

# Run comparison
python3 compare_atmos.py
