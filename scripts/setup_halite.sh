#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
halite_root="$project_root/engine/halite"
checkout="$halite_root/upstream"
build_source="$halite_root/build-source"
cpp_build="$halite_root/cpp-build"
bin_dir="$halite_root/bin"
revision="$(tr -d '[:space:]' < "$halite_root/REVISION")"
source_repo="${HALITE_SOURCE:-https://github.com/HaliteChallenge/Halite-III.git}"
cmake_bin="${CMAKE:-cmake}"
jobs="${JOBS:-4}"

if ! command -v "$cmake_bin" >/dev/null 2>&1; then
  echo "CMake is required; install it or set CMAKE to its executable path." >&2
  exit 1
fi

if [[ ! -d "$checkout/.git" ]]; then
  if [[ -e "$checkout" ]]; then
    echo "$checkout exists but is not a Git checkout; move it aside before setup." >&2
    exit 1
  fi
  git clone "$source_repo" "$checkout"
  git -C "$checkout" checkout --detach "$revision"
fi

actual="$(git -C "$checkout" rev-parse HEAD)"
if [[ "$actual" != "$revision" ]]; then
  echo "$checkout is at $actual, expected $revision." >&2
  exit 1
fi

if [[ ! -e "$build_source" ]]; then
  mkdir -p "$build_source"
  git -C "$checkout" archive "$revision" game_engine | tar -x -C "$build_source" --strip-components=1
  printf '%s\n' "$revision" > "$build_source/.mars-bot-lab-revision"
elif [[ ! -f "$build_source/.mars-bot-lab-revision" ]] || [[ "$(cat "$build_source/.mars-bot-lab-revision")" != "$revision" ]]; then
  echo "$build_source belongs to another or unknown revision; move it aside before setup." >&2
  exit 1
fi

# Optional offline cache: CMake validates every archive against upstream's SHA-256.
if [[ -n "${HALITE_DEPS_CACHE:-}" ]]; then
  mkdir -p "$build_source/external/src"
  for archive in v2.2.3.zip include.zip tclap-1.2.2.tar.gz v1.3.4.zip; do
    if [[ ! -f "$HALITE_DEPS_CACHE/$archive" ]]; then
      echo "Missing dependency archive: $HALITE_DEPS_CACHE/$archive" >&2
      exit 1
    fi
    cp "$HALITE_DEPS_CACHE/$archive" "$build_source/external/src/$archive"
  done
fi

"$cmake_bin" -S "$build_source" -B "$build_source" -DCMAKE_BUILD_TYPE=Release
# The old upstream version script otherwise reads the parent project's Git
# metadata and can replace its version with an empty string when tags are absent.
GIT_CEILING_DIRECTORIES="$halite_root" "$cmake_bin" --build "$build_source" --target halite -j "$jobs"
"$cmake_bin" -S "$checkout/starter_kits/C++" -B "$cpp_build" -DCMAKE_BUILD_TYPE=Release
"$cmake_bin" --build "$cpp_build" -j "$jobs"

if command -v go >/dev/null 2>&1; then
  mkdir -p "$bin_dir"
  (cd "$checkout/starter_kits/Go" && GO111MODULE=off go build -o "$bin_dir/MyBotGo" ./src)
else
  echo "Go is not installed; skipping the optional Go starter build."
fi

echo "Halite III $revision is ready. Run make demo."
