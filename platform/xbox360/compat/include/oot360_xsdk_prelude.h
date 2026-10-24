/* Included before every source of the Xbox 360 build (platform/xbox360/cmake/oot360-xsdk.cmake, -include).
   newlib's <sys/types.h> keeps BSD's "#define quad quad_t", which renames struct members called quad
   (Ocarina of Time's ColliderQuadDim) in some translation units and not others.
   IS_BIGENDIAN: libultraship's endianness.h defines it, but the game's C code (z64audio.h's AudioCmd,
   command_macros_base.h, color.h's Color_RGBA8_u32) tests it without including that header, so on a big-endian
   console those got the little-endian layouts: every audio command was misread and the game made silence (test 8). */
#ifndef OOT360_XSDK_PRELUDE_H
#define OOT360_XSDK_PRELUDE_H
#include <sys/types.h>
#undef quad
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__ && !defined(IS_BIGENDIAN)
#define IS_BIGENDIAN
#endif
#endif
