#!/bin/sh
# Run ccproxy's offline tests. No real API key is needed -- the suite starts its
# own mock upstream.
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python3" ]; then
  echo ".venv not found. Run start.sh once first -- it creates it."
  exit 1
fi

exec ./.venv/bin/python3 test_offline.py "$@"
