set(dynamic_files
 main.cpp
)
add_executable(dynamic ${dynamic_files})
target_link_libraries(dynamic PRIVATE DSF dl ${Boost_LIBRARIES})
target_compile_options(dynamic PRIVATE -fpermissive)
