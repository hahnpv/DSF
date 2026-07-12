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
# Table fixtures (table_1d.txt) live next to the sources; tell the test where.
target_compile_definitions(cpp_tablend_tests PRIVATE
    TEST_DATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
add_test(NAME cpp_tablend_tests COMMAND cpp_tablend_tests)

# Sim-kernel tests (clock, events) — no full sim loop required.
add_executable(cpp_kernel_tests test_kernel.cpp)
target_link_libraries(cpp_kernel_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_kernel_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_kernel_tests COMMAND cpp_kernel_tests)

# Multi-Sim isolation (R1: Sim-owned integrand registry + event bus).
add_executable(cpp_multisim_tests test_multisim.cpp)
target_link_libraries(cpp_multisim_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES} pthread)
target_include_directories(cpp_multisim_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_multisim_tests COMMAND cpp_multisim_tests)

# Shared deck loader (SimInput parsing, fallback rule, strict resolution).
add_executable(cpp_loader_tests test_loader.cpp)
target_link_libraries(cpp_loader_tests PRIVATE DSF dl ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_loader_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_loader_tests COMMAND cpp_loader_tests)

# Monte Carlo dispersion engine (transmitted draws, RNG fallback, strict).
add_executable(cpp_mc_tests test_monte_carlo.cpp)
target_link_libraries(cpp_mc_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_mc_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_mc_tests COMMAND cpp_mc_tests)

# Numerical validation: integrators vs canonical ODEs with known solutions.
add_executable(cpp_integrator_tests test_integrators.cpp)
target_link_libraries(cpp_integrator_tests PRIVATE DSF ${Boost_LIBRARIES} ${HDF5_LIBRARIES})
target_include_directories(cpp_integrator_tests PRIVATE ${Boost_INCLUDE_DIRS})
add_test(NAME cpp_integrator_tests COMMAND cpp_integrator_tests)
