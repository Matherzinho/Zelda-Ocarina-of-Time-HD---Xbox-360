#!/bin/bash
# SDL2 API on the Xbox 360: SDL-xenon (SDL3) with its SDL_* symbols renamed to SDL3X_*, plus sdl2-compat
# (patched to look SDL3 up in a static table) built as a static libSDL2.a. Both go into $OOT360_SYSROOT.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export OOT360_SYSROOT="${OOT360_SYSROOT:-$HOME/oot360-sysroot}"
SDL3_DIR="${SDL3_DIR:-$HOME/SDL-xenon}"
SDL2C="${SDL2COMPAT_SRC:-$HOME/deps-src/sdl2-compat}"
BUILD="${DEPS_BUILD:-$HOME/deps-build}/sdl"
P="$HOME/xsdk-gcc/bin/powerpc-xsdk-elf-"
mkdir -p "$BUILD" "$OOT360_SYSROOT/lib" "$OOT360_SYSROOT/include"

# 1. SDL3 with renamed symbols
"${P}nm" -g --defined-only "$SDL3_DIR/build-xsdk/libSDL3.a" 2>/dev/null | awk '$3 ~ /^SDL_/ {print $3" SDL3X_"substr($3,5)}' |
	sort -u >"$BUILD/sdl3-rename.map"
"${P}objcopy" --redefine-syms="$BUILD/sdl3-rename.map" "$SDL3_DIR/build-xsdk/libSDL3.a" "$OOT360_SYSROOT/lib/libSDL3X.a"
echo "renamed $(wc -l <"$BUILD/sdl3-rename.map") SDL3 symbols"

# 2. sdl2-compat, static
if ! git -C "$SDL2C" apply --check -R "$HERE/patches/sdl2-compat-xsdk.patch" 2>/dev/null; then
	git -C "$SDL2C" apply "$HERE/patches/sdl2-compat-xsdk.patch"
fi
CFLAGS=(-O2 -mcpu=cell -fno-pic -I"$HOME/xsdk/include" -I"$SDL2C/include" -I"$SDL2C/include/SDL2" -I"$SDL3_DIR/include"
	-DNDEBUG -w)
for f in src/sdl2_compat.c src/dynapi/SDL_dynapi.c; do
	"${P}gcc" "${CFLAGS[@]}" -c "$SDL2C/$f" -o "$BUILD/$(basename "$f" .c).o"
done
rm -f "$OOT360_SYSROOT/lib/libSDL2.a"
"${P}ar" rcs "$OOT360_SYSROOT/lib/libSDL2.a" "$BUILD"/sdl2_compat.o "$BUILD"/SDL_dynapi.o
mkdir -p "$OOT360_SYSROOT/include/SDL2"
cp -r "$SDL2C/include/SDL2/." "$OOT360_SYSROOT/include/SDL2/"
cp "$HERE/sdl2-headers/SDL_config_xsdk.h" "$OOT360_SYSROOT/include/SDL2/"
# Select it before the __unix__ branch (xsdk's GCC defines __unix__).
sed -i 's|^#if defined(__WIN32__)$|#if defined(__XSDK__)\n#include "SDL_config_xsdk.h"\n#elif defined(__WIN32__)|' "$OOT360_SYSROOT/include/SDL2/SDL_config.h"
echo "libSDL2.a + libSDL3X.a installed in $OOT360_SYSROOT"
