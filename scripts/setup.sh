#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
engine_dir="$project_root/engine/upstream"
revision="$(tr -d '[:space:]' < "$project_root/engine/REVISION")"
python_bin="${PYTHON:-python3.10}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "Python 3.10 is required. Set PYTHON to its executable path if needed." >&2
  exit 1
fi
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 10), "Expected Python 3.10"'

if [[ ! -d "$engine_dir/.git" ]]; then
  if [[ -e "$engine_dir" ]]; then
    echo "$engine_dir exists but is not a Git checkout; move it aside before setup." >&2
    exit 1
  fi
  git clone https://github.com/Lux-AI-Challenge/Lux-Design-S2.git "$engine_dir"
  git -C "$engine_dir" checkout --detach "$revision"
fi

actual="$(git -C "$engine_dir" rev-parse HEAD)"
if [[ "$actual" != "$revision" ]]; then
  echo "Upstream checkout is at $actual, expected $revision. Resolve this manually." >&2
  exit 1
fi

if [[ ! -x "$project_root/.venv/bin/python" ]]; then
  "$python_bin" -m venv "$project_root/.venv"
fi
"$project_root/.venv/bin/python" -m pip install -e "$engine_dir/luxai_s2"
"$project_root/.venv/bin/python" -m pip freeze > "$project_root/.venv/installed-packages.txt"
echo "Installed Lux AI Season 2 at $revision in .venv"

