set(dynamic_files
 main.cpp
)
ADD_EXECUTABLE(dynamic ${dynamic_files})
SET_TARGET_PROPERTIES(dynamic PROPERTIES LINKER_LANGUAGE C)
TARGET_LINK_LIBRARIES(dynamic DSF dl ${Boost_LIBRARIES})
set(CMAKE_CXX_FLAGS "-fpermissive")

# NOTE: you could create a statis binary by compiling with your model files
# first, delete the dynamic library section per instruction in main.cpp
# then update my_src_files to enumerate the files to be compiled together

# this creates as static executable
#set(my_src_files
# file1.cpp
# file2.cpp
#)
#ADD_EXECUTABLE(static main.cpp ${my_src_files})
#SET_TARGET_PROPERTIES(static PROPERTIES LINKER_LANGUAGE C)
#TARGET_LINK_LIBRARIES(static DSF dl ${Boost_LIBRARIES})
#set(CMAKE_CXX_FLAGS "-fpermissive")
