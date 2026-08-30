#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TOOLS="$ROOT/.audit_tools"
SRC="$TOOLS/src"
BUILD="$TOOLS/build"
BIN="$TOOLS/bin"
mkdir -p "$SRC" "$BUILD" "$BIN"

for command in curl tar cmake make; do
  command -v "$command" >/dev/null || { echo "missing build dependency: $command" >&2; exit 1; }
done

fetch() {
  local url=$1 archive=$2
  if [[ ! -s "$archive" ]]; then
    curl --retry 5 --retry-all-errors -L --fail --connect-timeout 20 "$url" -o "$archive"
  fi
}

if [[ ! -x "$BIN/cadical" ]]; then
  fetch https://codeload.github.com/arminbiere/cadical/tar.gz/refs/tags/rel-3.0.1 "$BUILD/cadical.tar.gz"
  [[ -d "$SRC/cadical-rel-3.0.1" ]] || tar -xzf "$BUILD/cadical.tar.gz" -C "$SRC"
  (cd "$SRC/cadical-rel-3.0.1" && ./configure && make -j"${AUDIT_JOBS:-4}")
  cp "$SRC/cadical-rel-3.0.1/build/cadical" "$BIN/cadical"
fi

if [[ ! -x "$BIN/kissat" ]]; then
  fetch https://codeload.github.com/arminbiere/kissat/tar.gz/refs/tags/rel-4.0.4 "$BUILD/kissat.tar.gz"
  [[ -d "$SRC/kissat-rel-4.0.4" ]] || tar -xzf "$BUILD/kissat.tar.gz" -C "$SRC"
  (cd "$SRC/kissat-rel-4.0.4" && ./configure && make -j"${AUDIT_JOBS:-4}")
  cp "$SRC/kissat-rel-4.0.4/build/kissat" "$BIN/kissat"
fi

if [[ ! -x "$BIN/drat-trim" ]]; then
  fetch https://codeload.github.com/marijnheule/drat-trim/tar.gz/2e3b2dc0ecf938addbd779d42877b6ed69d9a985 "$BUILD/drat-trim.tar.gz"
  [[ -d "$SRC/drat-trim-2e3b2dc0ecf938addbd779d42877b6ed69d9a985" ]] || tar -xzf "$BUILD/drat-trim.tar.gz" -C "$SRC"
  (cd "$SRC/drat-trim-2e3b2dc0ecf938addbd779d42877b6ed69d9a985" && make -j"${AUDIT_JOBS:-4}")
  cp "$SRC/drat-trim-2e3b2dc0ecf938addbd779d42877b6ed69d9a985/drat-trim" "$BIN/drat-trim"
fi

if [[ ! -x "$BIN/cryptominisat5" ]]; then
  command -v pkg-config >/dev/null || { echo "CryptoMiniSat requires pkg-config and GMP" >&2; exit 1; }
  fetch https://codeload.github.com/msoos/cryptominisat/tar.gz/refs/tags/release/v5.14.7 "$BUILD/cryptominisat.tar.gz"
  fetch https://codeload.github.com/meelgroup/cadical/tar.gz/refs/heads/master "$BUILD/cms-cadical.tar.gz"
  fetch https://codeload.github.com/meelgroup/cadiback/tar.gz/refs/heads/main "$BUILD/cadiback.tar.gz"
  [[ -d "$SRC/cryptominisat-release-v5.14.7" ]] || tar -xzf "$BUILD/cryptominisat.tar.gz" -C "$SRC"
  [[ -d "$SRC/cadical-master" ]] || tar -xzf "$BUILD/cms-cadical.tar.gz" -C "$SRC"
  [[ -d "$SRC/cadiback-main" ]] || tar -xzf "$BUILD/cadiback.tar.gz" -C "$SRC"
  mkdir -p "$BUILD/cms"
  cmake -S "$SRC/cryptominisat-release-v5.14.7" -B "$BUILD/cms" \
    -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTING=OFF -DBUILD_SHARED_LIBS=OFF -DSTATIC_BINARY=OFF \
    -DFETCHCONTENT_SOURCE_DIR_CADICAL="$SRC/cadical-master" \
    -DFETCHCONTENT_SOURCE_DIR_CADIBACK="$SRC/cadiback-main"
  cmake --build "$BUILD/cms" -j"${AUDIT_JOBS:-4}"
  cp "$BUILD/cms/cryptominisat5" "$BIN/cryptominisat5"
fi

if [[ ! -x "$BIN/z3" || ! -f "$BIN/libz3.dylib" && ! -f "$BIN/libz3.so" ]]; then
  command -v ninja >/dev/null || { echo "Z3 source build requires ninja" >&2; exit 1; }
  fetch https://codeload.github.com/Z3Prover/z3/tar.gz/refs/tags/z3-5.1.0 "$BUILD/z3-source.tar.gz"
  [[ -d "$SRC/z3-z3-5.1.0" ]] || tar -xzf "$BUILD/z3-source.tar.gz" -C "$SRC"
  cmake -G Ninja -S "$SRC/z3-z3-5.1.0" -B "$BUILD/z3-source" \
    -DCMAKE_BUILD_TYPE=Release -DZ3_BUILD_LIBZ3_SHARED=ON
  cmake --build "$BUILD/z3-source" -j"${AUDIT_JOBS:-4}"
  cp "$BUILD/z3-source/z3" "$BIN/z3"
  if [[ -f "$BUILD/z3-source/libz3.dylib" ]]; then
    cp "$BUILD/z3-source/libz3.dylib" "$BIN/libz3.dylib"
  else
    cp "$BUILD/z3-source/libz3.so" "$BIN/libz3.so"
  fi
fi

if [[ ! -x "$ROOT/.venv-audit/bin/python" ]]; then
  python3 -m venv "$ROOT/.venv-audit"
fi
"$ROOT/.venv-audit/bin/pip" install -q -r "$ROOT/requirements.txt"
