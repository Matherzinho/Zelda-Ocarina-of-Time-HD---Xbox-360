#!/bin/bash
# Builds Ship of Harkinian 9.3.1 for the Xbox 360 with xenosworks' xsdk, from nothing but the toolchain:
#   XSDK_HOME   folder holding xsdk/, xsdk-gcc/, SDL-xenon/ (built: build-xsdk/libSDL3.a) and glslang-xenon/
#               (default: $HOME, as xsdk's own guide lays them out)
#   WORK        where sources and builds go (default: ~/oot360-work)
#   JOBS        parallel compiles (default: nproc)
# The result is $WORK/build-soh/soh/soh.xex. No game data is read or written here: oot.o2r and soh.o2r are made on
# a PC with Ship of Harkinian 9.3.1 from the player's own ROM (docs/PLAYING.md).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
XSDK_HOME="${XSDK_HOME:-$HOME}"
WORK="${WORK:-$HOME/oot360-work}"
JOBS="${JOBS:-$(nproc)}"
export GIT_TERMINAL_PROMPT=0

SOH_TAG=9.3.1
export OOT360_SYSROOT="$WORK/sysroot"
export DEPS_SRC="$WORK/deps-src"
export DEPS_BUILD="$WORK/deps-build"
export SDL3_DIR="$XSDK_HOME/SDL-xenon"
export SDL2COMPAT_SRC="$DEPS_SRC/sdl2-compat"
GLSLANG="$XSDK_HOME/glslang-xenon/build/StandAlone/glslang"

step() { echo "== $*"; }

for d in xsdk xsdk-gcc SDL-xenon; do
	[ -d "$XSDK_HOME/$d" ] || { echo "missing $XSDK_HOME/$d (see xsdk's docs/GETTING_STARTED.md)" >&2; exit 1; }
done
[ -f "$SDL3_DIR/build-xsdk/libSDL3.a" ] || { echo "SDL-xenon isn't built: $SDL3_DIR/build-xsdk/libSDL3.a" >&2; exit 1; }
# xsdk's toolchain file finds the compiler at $HOME/xsdk-gcc.
export HOME="$XSDK_HOME"
mkdir -p "$WORK" "$DEPS_SRC"

clone() { # repo tag dir
	if [ ! -d "$3/.git" ]; then
		git clone -q --depth 1 -b "$2" "https://github.com/$1" "$3"
	fi
}

step "dependency sources"
clone madler/zlib v1.3.1 "$DEPS_SRC/zlib"
clone nih-at/libzip v1.11.4 "$DEPS_SRC/libzip"
clone leethomason/tinyxml2 10.0.0 "$DEPS_SRC/tinyxml2"
clone gabime/spdlog v1.16.0 "$DEPS_SRC/spdlog"
clone nlohmann/json v3.12.0 "$DEPS_SRC/json"
if [ ! -d "$SDL2COMPAT_SRC/.git" ]; then
	git clone -q https://github.com/libsdl-org/sdl2-compat "$SDL2COMPAT_SRC"
	git -C "$SDL2COMPAT_SRC" checkout -q d8198c2
fi
if [ ! -f "$DEPS_SRC/stb/stb_image.h" ]; then
	mkdir -p "$DEPS_SRC/stb"
	git -C "$DEPS_SRC/stb" init -q
	git -C "$DEPS_SRC/stb" fetch -q --depth 1 https://github.com/nothings/stb 0bc88af4de5fb022db643c2d8e549a0927749354
	git -C "$DEPS_SRC/stb" checkout -q FETCH_HEAD
fi

step "dependencies for powerpc-xsdk-elf"
if [ ! -f "$OOT360_SYSROOT/lib/libzip.a" ]; then
	"$HERE/deps/build-deps.sh"
fi
if [ ! -f "$OOT360_SYSROOT/lib/libSDL2.a" ]; then
	"$HERE/deps/build-sdl.sh"
fi

step "Ship of Harkinian $SOH_TAG"
SOH="$WORK/Shipwright"
if [ ! -d "$SOH/.git" ]; then
	git clone -q --depth 1 -b "$SOH_TAG" --recurse-submodules --shallow-submodules \
		https://github.com/HarbourMasters/Shipwright "$SOH"
	git -C "$SOH" apply "$HERE/patches/shipwright-$SOH_TAG-xsdk.patch"
	git -C "$SOH/libultraship" apply "$HERE/patches/libultraship-da6daf1-xsdk.patch"
fi

step "configure"
BUILD="$WORK/build-soh"
mkdir -p "$BUILD/_deps/stb"
cp "$DEPS_SRC/stb/stb_image.h" "$BUILD/_deps/stb/"
cmake -S "$SOH" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_TOOLCHAIN_FILE="$HERE/cmake/oot360-xsdk.cmake" -DOOT360_SYSROOT="$OOT360_SYSROOT" \
	-DXSDK_GLSLANG="$GLSLANG" >"$WORK/configure.log"

step "build"
cmake --build "$BUILD" -j "$JOBS"
ls -la "$BUILD/soh/soh.xex"
