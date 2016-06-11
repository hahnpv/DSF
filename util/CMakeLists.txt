set(util_source_files
  file/get_unique_file.h
  fptr.h
  gauss.h
  math/constants.h
  math/mat3.cpp
  math/mat3.h
  math/sign.h
  math/vec3.cpp
  math/vec3.h
  parse.h
  sign.h
  tbl/tbl.cpp
  tbl/tbl.h
  tbl/tbl2d.cpp
  tbl/tbl2d.h
  TFunctor.h
  xml/node.h
  xml/xml.cpp
  xml/xml.h
  xml/xmlnode.h
  xml/xml_reader.h
)
add_library(util ${util_source_files})

SET_TARGET_PROPERTIES(util PROPERTIES LINKER_LANGUAGE C)

set(CMAKE_CXX_FLAGS "-fpermissive")
