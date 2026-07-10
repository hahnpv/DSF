# C++ unit tests for the DSF core (registered with CTest).
#
# These link the DSF shared library and exercise the utility layer (tables,
# math) and, as more are added, the sim kernel. Run with `ctest` from build/.

add_executable(cpp_util_tests test_util.cpp)
target_link_libraries(cpp_util_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_util_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_util_tests COMMAND cpp_util_tests)

add_executable(cpp_tablend_tests test_tablend.cpp)
target_link_libraries(cpp_tablend_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_tablend_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_tablend_tests COMMAND cpp_tablend_tests)

# Sim-kernel tests (clock, events) — no full sim loop required.
add_executable(cpp_kernel_tests test_kernel.cpp)
target_link_libraries(cpp_kernel_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_kernel_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_kernel_tests COMMAND cpp_kernel_tests)

# Numerical validation: integrators vs canonical ODEs with known solutions.
add_executable(cpp_integrator_tests test_integrators.cpp)
target_link_libraries(cpp_integrator_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_integrator_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_integrator_tests COMMAND cpp_integrator_tests)
