set(util_source_files
  file/get_unique_file.h
  fptr.h
  gauss.h
  math/constants.h
  math/number.h
  math/mat3.cpp
  math/mat3.h
  math/vec3.cpp
  math/vec3.h
  parse.h
  sign.h
  tbl/tbl.cpp
  tbl/tbl.h
  tbl/tbl2d.cpp
  tbl/tbl2d.h
  tbl/tablend.cpp
  tbl/tablend.h
  TFunctor.h
  xml/xml.h
  xml/xml.cpp
)
add_library(util ${util_source_files})
target_compile_options(util PRIVATE -fpermissive)
