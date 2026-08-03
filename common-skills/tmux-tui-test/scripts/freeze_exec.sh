#!/bin/sh

set -eu

freeze_bin=${FREEZE_BIN:-}
if [ -z "$freeze_bin" ]; then
  if ! freeze_bin=$(which freeze 2>/dev/null); then
    echo "freeze_exec.sh: freeze is not installed or not on PATH" >&2
    exit 127
  fi
elif [ "${freeze_bin#*/}" = "$freeze_bin" ]; then
  if ! freeze_bin=$(which "$freeze_bin" 2>/dev/null); then
    echo "freeze_exec.sh: FREEZE_BIN is not on PATH: $FREEZE_BIN" >&2
    exit 127
  fi
fi

if [ ! -x "$freeze_bin" ]; then
  echo "freeze_exec.sh: freeze executable is not executable: $freeze_bin" >&2
  exit 126
fi

exec "$freeze_bin" --language ansi "$@"
