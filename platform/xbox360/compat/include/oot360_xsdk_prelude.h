/* Included before every source of the Xbox 360 build (platform/xbox360/cmake/oot360-xsdk.cmake, -include).
   newlib's <sys/types.h> keeps BSD's "#define quad quad_t", which renames struct members called quad
   (Ocarina of Time's ColliderQuadDim) in some translation units and not others. */
#ifndef OOT360_XSDK_PRELUDE_H
#define OOT360_XSDK_PRELUDE_H
#include <sys/types.h>
#undef quad
#endif
