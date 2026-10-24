#!/bin/bash
# Cross-builds the libraries libultraship/SoH need for powerpc-xsdk-elf into $OOT360_SYSROOT.
# Sources are expected in $DEPS_SRC (cloned at the tags listed in deps/VERSIONS).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TC="$HERE/../cmake/oot360-xsdk.cmake"
export OOT360_SYSROOT="${OOT360_SYSROOT:-$HOME/oot360-sysroot}"
DEPS_SRC="${DEPS_SRC:-$HOME/deps-src}"
BUILD="${DEPS_BUILD:-$HOME/deps-build}"
mkdir -p "$OOT360_SYSROOT" "$BUILD"

cm() { # name, extra cmake args...
	local name=$1; shift
	echo "== $name"
	cmake -S "$DEPS_SRC/$name" -B "$BUILD/$name" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$TC" \
		-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$OOT360_SYSROOT" -DBUILD_SHARED_LIBS=OFF "$@" \
		>"$BUILD/$name.configure.log" 2>&1 || { tail -30 "$BUILD/$name.configure.log"; exit 1; }
	cmake --build "$BUILD/$name" >"$BUILD/$name.build.log" 2>&1 || { tail -40 "$BUILD/$name.build.log"; exit 1; }
	cmake --install "$BUILD/$name" >/dev/null
}

[ -f "$OOT360_SYSROOT/lib/libzip.a" ] || cm zlib -DZLIB_BUILD_EXAMPLES=OFF
[ -f "$OOT360_SYSROOT/lib/libzip.a" ] || cm libzip -DENABLE_BZIP2=OFF -DENABLE_LZMA=OFF -DENABLE_ZSTD=OFF -DENABLE_OPENSSL=OFF -DENABLE_GNUTLS=OFF \
	-DENABLE_MBEDTLS=OFF -DENABLE_COMMONCRYPTO=OFF -DENABLE_WINDOWS_CRYPTO=OFF -DBUILD_TOOLS=OFF \
	-DBUILD_REGRESS=OFF -DBUILD_OSSFUZZ=OFF -DBUILD_EXAMPLES=OFF -DBUILD_DOC=OFF \
	-DZLIB_ROOT="$OOT360_SYSROOT" -DZLIB_USE_STATIC_LIBS=ON
cm tinyxml2 -Dtinyxml2_BUILD_TESTING=OFF
cm json -DJSON_BuildTests=OFF
cm spdlog -DSPDLOG_BUILD_EXAMPLE=OFF -DSPDLOG_BUILD_TESTS=OFF -DSPDLOG_NO_TLS=ON -DSPDLOG_NO_THREAD_ID=ON
# Audio for custom sequences (soh/mixer.c, AudioSampleFactory.cpp): Ogg, Vorbis, Opus, and opusfile without HTTP.
cm ogg -DINSTALL_DOCS=OFF -DBUILD_TESTING=OFF
cm vorbis -DOGG_ROOT="$OOT360_SYSROOT" -DBUILD_TESTING=OFF
cm opus -DOPUS_BUILD_PROGRAMS=OFF -DOPUS_BUILD_TESTING=OFF -DOPUS_DISABLE_INTRINSICS=ON -DOPUS_INSTALL_PKG_CONFIG_MODULE=OFF
echo "== opusfile"
P="$HOME/xsdk-gcc/bin/powerpc-xsdk-elf-"
mkdir -p "$BUILD/opusfile" "$OOT360_SYSROOT/include/opus"
for f in info internal opusfile stream; do
	"${P}gcc" -O2 -mcpu=cell -fno-pic -I"$HOME/xsdk/include" -I"$OOT360_SYSROOT/include" -I"$OOT360_SYSROOT/include/opus" \
		-I"$DEPS_SRC/opusfile/include" -DOP_DISABLE_HTTP -DOP_DISABLE_FLOAT_API=0 -w \
		-c "$DEPS_SRC/opusfile/src/$f.c" -o "$BUILD/opusfile/$f.o"
done
rm -f "$OOT360_SYSROOT/lib/libopusfile.a"
"${P}ar" rcs "$OOT360_SYSROOT/lib/libopusfile.a" "$BUILD"/opusfile/*.o
cp "$DEPS_SRC/opusfile/include/opusfile.h" "$OOT360_SYSROOT/include/opus/"
echo "deps installed in $OOT360_SYSROOT"
