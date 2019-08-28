set(bouncy_source_files
 bouncy.cpp
)
ADD_LIBRARY(bouncy SHARED ${bouncy_source_files})
SET_TARGET_PROPERTIES(bouncy PROPERTIES LINKER_LANGUAGE C)
TARGET_LINK_LIBRARIES(bouncy DSF)
set(CMAKE_CXX_FLAGS "-fpermissive")
CONFIGURE_FILE(bouncy.xml bouncy.xml COPYONLY)
