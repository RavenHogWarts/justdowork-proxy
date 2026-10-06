#!/bin/sh
# ---------------------------------------------------------------------------
#  Start ccproxy on macOS / Linux.
#
#      sh start.sh
#
#  The first run creates a local .venv and installs flask + requests into it.
#  Nothing is installed globally, and nothing outside this folder is touched.
# ---------------------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "!! Python 3 was not found."
  echo "   macOS:  brew install python3"
  echo "   or download it from https://www.python.org/downloads/"
  exit 1
fi

if [ ! -x ".venv/bin/python3" ]; then
  echo "Creating .venv (first run only, this takes a minute) ..."
  "$PY" -m venv .venv || exit 1
  ./.venv/bin/python3 -m pip install --quiet --upgrade pip || exit 1
  echo "Installing dependencies ..."
  ./.venv/bin/python3 -m pip install --quiet -r requirements.txt || exit 1
fi

# ccproxy itself also checks this, but failing here gives a clearer message.
if [ -z "$UPSTREAM_API_KEY" ] && grep -q '"api_key": ""' config.json 2>/dev/null; then
  echo "!! UPSTREAM_API_KEY is not set."
  echo "   Run:  export UPSTREAM_API_KEY='sk-...'"
  echo "   or put the key into config.json as \"api_key\": \"sk-...\""
  exit 1
fi

echo
echo "Starting ccproxy ... (the exact URL is printed on the next line)"
echo "Press Ctrl+C to stop."
echo

exec ./.venv/bin/python3 ccproxy.py
