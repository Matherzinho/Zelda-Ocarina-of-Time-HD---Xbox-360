# Wraps xsdk's toolchain file and adds this project's dependency sysroot (built by deps/build-deps.sh).
# Paths: XSDK_ROOT_DIR (default ~/xsdk) and OOT360_SYSROOT (default ~/oot360-sysroot).
if(NOT DEFINED ENV{XSDK_ROOT_DIR})
	set(ENV{XSDK_ROOT_DIR} "$ENV{HOME}/xsdk")
endif()
include("$ENV{XSDK_ROOT_DIR}/cmake/xsdk.cmake")
if(DEFINED ENV{OOT360_SYSROOT})
	set(OOT360_SYSROOT "$ENV{OOT360_SYSROOT}")
else()
	set(OOT360_SYSROOT "$ENV{HOME}/oot360-sysroot")
endif()
list(APPEND CMAKE_FIND_ROOT_PATH "${OOT360_SYSROOT}")
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES OOT360_SYSROOT)
# POSIX headers xsdk's newlib lacks, as stubs (platform/xbox360/compat/include).
get_filename_component(OOT360_COMPAT_INCLUDE "${CMAKE_CURRENT_LIST_DIR}/../compat/include" ABSOLUTE)
list(APPEND CMAKE_C_STANDARD_INCLUDE_DIRECTORIES "${OOT360_COMPAT_INCLUDE}")
list(APPEND CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES "${OOT360_COMPAT_INCLUDE}")
string(APPEND CMAKE_C_FLAGS_INIT " -include ${OOT360_COMPAT_INCLUDE}/oot360_xsdk_prelude.h")
string(APPEND CMAKE_CXX_FLAGS_INIT " -include ${OOT360_COMPAT_INCLUDE}/oot360_xsdk_prelude.h")
