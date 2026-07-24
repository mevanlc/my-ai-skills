#!/usr/bin/env bash
#
# bgshells — find and clean up LIVE Claude Code background shells.
#
# Claude Code runs each Bash(run_in_background) shell detached, streaming its
# output to <session-dir>/tasks/<taskid>.output. The harness can read, stop, or
# wait on a task once you have its id — but it exposes NO way to enumerate which
# background shells are still running. After a context compaction their ids and
# pids are gone from the model's memory, so leaked waiters (a stuck
# `until ...; do sleep; done` poller, an orphaned test worker) pile up unseen.
#
# This finds them from the OS side: any process still holding a
# `.../tasks/*.output` file open is a live background shell. Each is correlated
# with ps (age, parent, command) so you can spot and kill the stale ones.
#
# Usage:
#   bgshells [list]                 # table of live background shells (default)
#   bgshells stale [DUR]            # only those older than DUR (default 30m)
#   bgshells kill <pid|taskid>...   # TERM then KILL specific shells
#   bgshells reap [DUR] [--yes]     # kill all stale; without --yes it dry-runs
#
# DUR: a duration like 45s, 30m, 2h. A bare number is minutes.
#
# Notes:
#   * Prefer the harness-native `TaskStop <taskid>` when you still have the id;
#     this is the OS-level fallback for when you don't (e.g. post-compaction).
#   * Only your own processes are inspected. Task paths with spaces are not
#     supported (Claude session dirs don't contain spaces).

set -uo pipefail

mypgid=$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')

# ---- helpers ---------------------------------------------------------------

etime_to_secs() {  # parse ps ELAPSED: [[dd-]hh:]mm:ss -> seconds
  local e="$1" days=0 rest a b c
  if [[ "$e" == *-* ]]; then days="${e%%-*}"; rest="${e#*-}"; else rest="$e"; fi
  IFS=: read -r a b c <<<"$rest"
  if [ -n "${c:-}" ]; then
    echo $(( ((10#$days*24 + 10#$a)*60 + 10#$b)*60 + 10#$c ))
  else
    echo $(( (10#$days*24*60 + 10#$a)*60 + 10#$b ))
  fi
}

dur_to_secs() {  # 45s / 30m / 2h / bare-minutes -> seconds
  local d="$1"
  case "$d" in
    *s) echo $(( ${d%s} )) ;;
    *m) echo $(( ${d%m} * 60 )) ;;
    *h) echo $(( ${d%h} * 3600 )) ;;
    *)  echo $(( d * 60 )) ;;
  esac
}

snippet() {  # strip the shell-snapshot wrapper, show the eval'd body
  local c="$1"
  if [[ "$c" == *"eval '"* ]]; then
    c="${c#*eval \'}"
    c="${c%%\' < /dev/null*}"
  fi
  printf '%.150s' "$c"
}

# Live processes holding a .../tasks/*.output open -> "PID\tTASKID\tPATH".
collect() {
  lsof -nP -u "$(id -un)" 2>/dev/null \
  | awk '
      {
        path=$9; for (i=10;i<=NF;i++) path=path" "$i
        if (path ~ /\.output$/ && index(path,"/tasks/")) {
          n=split(path,a,"/"); f=a[n]; sub(/\.output$/,"",f)
          print $2 "\t" f "\t" path
        }
      }' \
  | sort -u
}

# collect + enrich (ppid, elapsed, command), excluding our own process group.
# Emits "PID\tPPID\tELAPSED\tTASKID\tCOMMAND".
rows() {
  local pid taskid path info pgid ppid etime cmd
  while IFS=$'\t' read -r pid taskid path; do
    info=$(ps -o pgid=,ppid=,etime= -p "$pid" 2>/dev/null) || continue
    [ -z "$info" ] && continue
    read -r pgid ppid etime <<<"$info"
    [ "$pgid" = "$mypgid" ] && continue
    cmd=$(ps -o command= -p "$pid" 2>/dev/null)
    printf '%s\t%s\t%s\t%s\t%s\n' "$pid" "$ppid" "$etime" "$taskid" "$cmd"
  done < <(collect) | sort -u
}

# ---- subcommands -----------------------------------------------------------

cmd_list() {  # $1 = minimum age in seconds (0 = all)
  local minsecs="${1:-0}" found=0 pid ppid etime taskid cmd s
  while IFS=$'\t' read -r pid ppid etime taskid cmd; do
    [ -z "${pid:-}" ] && continue
    if [ "$minsecs" -gt 0 ]; then
      s=$(etime_to_secs "$etime"); [ "$s" -lt "$minsecs" ] && continue
    fi
    if [ "$found" -eq 0 ]; then
      printf '%-7s %-7s %-11s %-13s %s\n' PID PPID ELAPSED TASKID WAITING-ON/CMD
      found=1
    fi
    printf '%-7s %-7s %-11s %-13s %s\n' "$pid" "$ppid" "$etime" "$taskid" "$(snippet "$cmd")"
  done < <(rows)
  if [ "$found" -eq 0 ]; then
    if [ "$minsecs" -gt 0 ]; then
      echo "(no live background shells older than the threshold)"
    else
      echo "(no live background shells)"
    fi
  fi
}

pids_for() {  # resolve pid/taskid args -> pids that are actually live
  local map arg pid ppid etime taskid cmd
  map=$(rows)
  for arg in "$@"; do
    if [[ "$arg" =~ ^[0-9]+$ ]]; then
      echo "$arg"
    else
      while IFS=$'\t' read -r pid ppid etime taskid cmd; do
        [ "$taskid" = "$arg" ] && echo "$pid"
      done <<<"$map"
    fi
  done | sort -un
}

do_kill() {  # TERM, then KILL survivors; $@ = pids
  local pid alive=()
  [ "$#" -eq 0 ] && { echo "nothing to kill"; return 0; }
  kill "$@" 2>/dev/null || true
  sleep 1
  for pid in "$@"; do
    kill -0 "$pid" 2>/dev/null && alive+=("$pid")
  done
  if [ "${#alive[@]}" -gt 0 ]; then
    kill -9 "${alive[@]}" 2>/dev/null || true
    echo "force-killed: ${alive[*]}"
  fi
  echo "killed: $*"
}

cmd_kill() {
  [ "$#" -eq 0 ] && { echo "usage: bgshells kill <pid|taskid>..." >&2; exit 2; }
  local pids; pids=$(pids_for "$@")
  [ -z "$pids" ] && { echo "no live background shells matched: $*"; return 0; }
  # shellcheck disable=SC2086
  do_kill $pids
}

cmd_reap() {
  local minsecs yes=0 arg dur="30m"
  for arg in "$@"; do
    case "$arg" in
      --yes|-y) yes=1 ;;
      *) dur="$arg" ;;
    esac
  done
  minsecs=$(dur_to_secs "$dur")
  local pids=() pid ppid etime taskid cmd s
  while IFS=$'\t' read -r pid ppid etime taskid cmd; do
    [ -z "${pid:-}" ] && continue
    s=$(etime_to_secs "$etime"); [ "$s" -lt "$minsecs" ] && continue
    pids+=("$pid")
  done < <(rows)
  if [ "${#pids[@]}" -eq 0 ]; then
    echo "(nothing older than $dur to reap)"; return 0
  fi
  echo "stale background shells (older than $dur):"
  cmd_list "$minsecs"
  if [ "$yes" -eq 1 ]; then
    echo "---"
    do_kill "${pids[@]}"
  else
    echo "---"
    echo "dry run — re-run with --yes to kill: bgshells reap $dur --yes"
  fi
}

# ---- dispatch --------------------------------------------------------------

case "${1:-list}" in
  list|ls|"")        cmd_list 0 ;;
  stale)             shift; cmd_list "$(dur_to_secs "${1:-30m}")" ;;
  kill|stop)         shift; cmd_kill "$@" ;;
  reap|clean)        shift; cmd_reap "$@" ;;
  -h|--help|help)    awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0" ;;
  *)                 echo "unknown subcommand: $1" >&2
                     echo "try: bgshells [list|stale|kill|reap|help]" >&2; exit 2 ;;
esac
