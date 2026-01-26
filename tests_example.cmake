# Example: Add this at the end of CMakeLists.txt to create tests

# Test 1: Run bouncy example
add_test(
    NAME bouncy_example
    COMMAND dynamic ${CMAKE_SOURCE_DIR}/examples/bouncy/bouncy.xml
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/examples/dynamic
)

# Test 2: Run sixdof orbital example (if sixdof is available)
if(DEFINED SIXDOF_DIR)
    add_test(
        NAME orbital_example
        COMMAND dynamic ${CMAKE_SOURCE_DIR}/examples/sixdof/dynamic/orbital.xml
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/examples/dynamic
    )
endif()

# Set test properties (optional)
set_tests_properties(bouncy_example PROPERTIES
    TIMEOUT 10
    PASS_REGULAR_EXPRESSION "Sim run time:"
)
