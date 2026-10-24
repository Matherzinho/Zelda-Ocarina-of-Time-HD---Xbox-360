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

cm zlib -DZLIB_BUILD_EXAMPLES=OFF
cm libzip -DENABLE_BZIP2=OFF -DENABLE_LZMA=OFF -DENABLE_ZSTD=OFF -DENABLE_OPENSSL=OFF -DENABLE_GNUTLS=OFF \
	-DENABLE_MBEDTLS=OFF -DENABLE_COMMONCRYPTO=OFF -DENABLE_WINDOWS_CRYPTO=OFF -DBUILD_TOOLS=OFF \
	-DBUILD_REGRESS=OFF -DBUILD_OSSFUZZ=OFF -DBUILD_EXAMPLES=OFF -DBUILD_DOC=OFF \
	-DZLIB_ROOT="$OOT360_SYSROOT" -DZLIB_USE_STATIC_LIBS=ON
cm tinyxml2 -Dtinyxml2_BUILD_TESTING=OFF
cm json -DJSON_BuildTests=OFF
cm spdlog -DSPDLOG_BUILD_EXAMPLE=OFF -DSPDLOG_BUILD_TESTS=OFF -DSPDLOG_NO_TLS=ON -DSPDLOG_NO_THREAD_ID=ON
echo "deps installed in $OOT360_SYSROOT"
