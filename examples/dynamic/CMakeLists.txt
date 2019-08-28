set(dynamic_files
 main.cpp
)
ADD_EXECUTABLE(dynamic ${dynamic_files})
SET_TARGET_PROPERTIES(dynamic PROPERTIES LINKER_LANGUAGE C)
TARGET_LINK_LIBRARIES(dynamic DSF dl ${Boost_LIBRARIES})
set(CMAKE_CXX_FLAGS "-fpermissive")