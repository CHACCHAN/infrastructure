#!/usr/bin/env bash
# Runs sandboxed OpenCode workers on throwaway copies of this repository (see SKILL.md).
set -euo pipefail

: "${DELEGATE_DIR:?set DELEGATE_DIR to a scratch directory}"
REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
CONFIG="$REPO/.agents/opencode/worker.json"
PORT=${DELEGATE_PORT:-47811}
URL="http://127.0.0.1:$PORT"
PID_FILE="$DELEGATE_DIR/server.pid"

usage() {
  echo "usage: $0 start | prepare <task> | run <task> <model> <brief-file> | continue <task> <brief-file> | result <task> | diff <task> | stop" >&2
  exit 2
}

workspace() {
  local ws="$DELEGATE_DIR/ws/${1:?task name}"
  [ -d "$ws/repo" ] || { echo "no workspace for task $1; run prepare first" >&2; exit 1; }
  echo "$ws"
}

server_alive() {
  [ -s "$PID_FILE" ] && ps -o args= -p "$(cat "$PID_FILE")" 2>/dev/null | grep -q 'opencode serve'
}

api_status() {
  curl -s -o /dev/null -w '%{http_code}' -u "opencode:$(cat "$DELEGATE_DIR/password" 2>/dev/null)" "$URL/openapi.json" || true
}

session_id() {
  python3 -I - "$1/run.jsonl" 2>/dev/null <<'PY' || true
import json, sys
session = ""
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        session = json.loads(line).get("sessionID") or session
    except ValueError:
        continue
print(session)
PY
}

ask() {
  local ws=$1 brief=$2
  shift 2
  server_alive || { echo "no server for this DELEGATE_DIR; run start first" >&2; exit 1; }
  (cd "$ws/repo" && OPENCODE_PASSWORD="$(cat "$DELEGATE_DIR/password")" \
    timeout "${DELEGATE_TIMEOUT:-7200}" opencode run --server "$URL" --agent worker --format json "$@" -- "$(cat "$brief")") \
    >> "$ws/run.jsonl" 2>> "$ws/run.err" || echo "opencode run exited with $?" >> "$ws/run.err"
}

show_result() {
  local ws=$1 outside ignored
  if [ -s "$ws/run.jsonl" ]; then
    python3 -I - "$ws/run.jsonl" <<'PY'
import json, sys
last, denied, failed = "", 0, 0
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        part = json.loads(line).get("part") or {}
    except ValueError:
        continue
    if part.get("type") == "text" and part.get("text"):
        last = part["text"]
    elif part.get("type") == "tool" and (part.get("state") or {}).get("status") == "error":
        failed += 1
        denied += "Permission denied" in str(part["state"].get("error"))
print(last or "(no final message)")
print(f"\n[tool errors: {failed}, of which permission denials: {denied}]")
PY
  else
    echo "(no output recorded)"
  fi
  if [ -s "$ws/run.err" ]; then echo "[stderr]"; tail -n 5 "$ws/run.err"; fi
  git -C "$ws/repo" add -A -N
  git -C "$ws/repo" diff --stat
  outside=$(git -C "$ws/repo" diff --name-only | grep -Ev '^(docs|roles|playbooks|inventory)/' || true)
  if [ -n "$outside" ]; then printf '[changed outside docs/ roles/ playbooks/ inventory/]\n%s\n' "$outside"; fi
  ignored=$(git -C "$ws/repo" status --porcelain --ignored | sed -n 's/^!! //p')
  if [ -n "$ignored" ]; then printf '[ignored by git, not in the diff]\n%s\n' "$ignored"; fi
}

cmd=${1:-}
[ $# -gt 0 ] && shift
case "$cmd" in
  start)
    mkdir -p "$DELEGATE_DIR" && chmod 700 "$DELEGATE_DIR"
    hash=$(sha256sum "$CONFIG" | cut -d' ' -f1)
    if server_alive; then
      [ "$(cat "$DELEGATE_DIR/config.sha256" 2>/dev/null)" = "$hash" ] \
        || { echo "worker.json changed since the server started; run stop, then start" >&2; exit 1; }
      echo "server already running at $URL"
      exit 0
    fi
    [ "$(api_status)" = 000 ] || { echo "port $PORT is in use by another process; set DELEGATE_PORT" >&2; exit 1; }
    [ -s "$DELEGATE_DIR/password" ] || (umask 077 && head -c 32 /dev/urandom | base64 | tr -d '/+=\n' > "$DELEGATE_DIR/password")
    echo "$hash" > "$DELEGATE_DIR/config.sha256"
    # A minimal environment keeps credentials (vault password file, SSH agent, tokens) away from the workers;
    # OPENCODE_DISABLE_PROJECT_CONFIG stops a copy's own opencode.json and .opencode/ plugins from loading.
    env -i HOME="$HOME" PATH="$PATH" USER="${USER:-$(id -un)}" SHELL=/bin/bash LANG="${LANG:-C.UTF-8}" \
      OPENCODE_CONFIG="$CONFIG" OPENCODE_DB="$DELEGATE_DIR/opencode.db" \
      OPENCODE_DISABLE_PROJECT_CONFIG=1 OPENCODE_DISABLE_AUTOUPDATE=1 OPENCODE_DISABLE_FILEWATCHER=1 \
      OPENCODE_SERVER_PASSWORD="$(cat "$DELEGATE_DIR/password")" \
      nohup opencode serve --hostname 127.0.0.1 --port "$PORT" > "$DELEGATE_DIR/server.log" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in $(seq 1 60); do
      [ "$(api_status)" = 200 ] && { echo "server ready at $URL"; exit 0; }
      sleep 0.5
    done
    echo "server did not start; see $DELEGATE_DIR/server.log" >&2
    exit 1
    ;;
  prepare)
    ws="$DELEGATE_DIR/ws/${1:?task name}"
    [ ! -e "$ws" ] || { echo "$ws already exists" >&2; exit 1; }
    mkdir -p "$ws"
    # History plus the current working tree; files ignored by git stay out of the copy.
    git clone -q --no-checkout --no-hardlinks "$REPO" "$ws/repo"
    git -C "$REPO" ls-files -z -co --exclude-standard \
      | (cd "$REPO" && tar --null --ignore-failed-read -T - -cf -) | tar -xf - -C "$ws/repo"
    git -C "$ws/repo" add -A
    git -C "$ws/repo" -c user.name=delegate -c user.email=delegate@localhost commit -q --no-verify --allow-empty -m base
    echo "$ws/repo"
    ;;
  run)
    ws=$(workspace "${1:-}")
    ask "$ws" "${3:?brief file}" -m "litellm/${2:?model}" --title "$1"
    show_result "$ws"
    ;;
  continue)
    ws=$(workspace "${1:-}")
    session=$(session_id "$ws")
    [ -n "$session" ] || { echo "no session recorded for task $1" >&2; exit 1; }
    ask "$ws" "${2:?brief file}" -s "$session"
    show_result "$ws"
    ;;
  result)
    show_result "$(workspace "${1:-}")"
    ;;
  diff)
    ws=$(workspace "${1:-}")
    git -C "$ws/repo" add -A -N
    git -C "$ws/repo" diff --binary
    ;;
  stop)
    if server_alive; then
      kill "$(cat "$PID_FILE")"
      echo "server stopped"
    else
      echo "no server of this DELEGATE_DIR is running"
    fi
    rm -f "$PID_FILE"
    ;;
  *) usage ;;
esac
