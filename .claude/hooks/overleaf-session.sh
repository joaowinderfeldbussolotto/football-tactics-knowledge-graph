#!/bin/bash
# Claude Code on the web: give the claudeleaf MCP server the Overleaf session it needs.
#
# claudeleaf signs in once, by hand, in a browser (`npx claudeleaf login`), and caches the session in
# ~/.claudeleaf/session.json. A cloud session has no browser, so the file is rebuilt here from the
# environment variable CLAUDELEAF_SESSION_JSON (the content of that file, kept as an environment
# secret). The content is never printed: this script's output goes into the session's context.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

home="${CLAUDELEAF_HOME:-$HOME/.claudeleaf}"

if [ -z "${CLAUDELEAF_SESSION_JSON:-}" ]; then
  if [ -f "$home/session.json" ]; then
    echo "claudeleaf: using the session already in $home/session.json"
  else
    echo "claudeleaf: CLAUDELEAF_SESSION_JSON is not set, so the Overleaf tools will answer 'No Overleaf session found'. See paper/OVERLEAF.md."
  fi
  exit 0
fi

mkdir -p "$home"
chmod 700 "$home"
# keep only a well-formed session: a JSON object with the Overleaf cookie
if ! printf '%s' "$CLAUDELEAF_SESSION_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
assert isinstance(data.get("cookies"), dict) and data["cookies"].get("overleaf_session2")
' 2>/dev/null; then
  echo "claudeleaf: CLAUDELEAF_SESSION_JSON is not a valid session file (expected {\"baseUrl\", \"cookies\": {\"overleaf_session2\": ...}}); nothing was written. See paper/OVERLEAF.md."
  exit 0
fi
umask 077
printf '%s' "$CLAUDELEAF_SESSION_JSON" > "$home/session.json.tmp"
mv "$home/session.json.tmp" "$home/session.json"
echo "claudeleaf: Overleaf session installed in $home/session.json (mode 600)"
