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
# util is linked into the shared libDSF.so, so its objects must be
# position-independent. Without this, the day a util-only source defines a
# symbol, linking libDSF.so fails with an R_X86_64_PC32 relocation error.
set_target_properties(util PROPERTIES POSITION_INDEPENDENT_CODE ON)
