# Copyright (c) 2026 abdurrehmandaudi
# Required Notice: Copyright (c) 2026 abdurrehmandaudi -- justdowork-proxy
# Licensed under the PolyForm Noncommercial License 1.0.0 -- commercial
# use is not permitted without a separate written commercial license.
# See LICENSE or https://polyformproject.org/licenses/noncommercial/1.0.0
# ---------------------------------------------------------------------------
#  Docker image for ccproxy.
#
#      docker build -t ccproxy .
#      docker run --rm -p 8181:8181 -e UPSTREAM_API_KEY='sk-...' ccproxy
#
#  Inside the container ccproxy binds 0.0.0.0 so the port can be mapped.
#  All settings can still be overridden via environment variables
#  (UPSTREAM_API_KEY, TARGET_URL, PORT) or a mounted config.json.
#  See DOCKER.md for the full instructions.
# ---------------------------------------------------------------------------

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LISTEN_HOST=0.0.0.0 \
    PORT=8181 \
    CCPROXY_DATA_DIR=/app/data

WORKDIR /app

# dependencies first, so code changes don't invalidate this layer
# waitress = production WSGI server; ccproxy falls back to Flask's dev
# server automatically when it is missing
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt waitress

COPY LICENSE README.md ./
COPY ccproxy.py dashboard.py config.json ./

# ccproxy writes its runtime data (the saved fallback key in .env, the
# request log, and debug_dump/) into CCPROXY_DATA_DIR = /app/data. Keeping
# it separate from the code lets a volume persist it across re-creations
# without masking the app. Make both owned by the runtime user.
RUN useradd --system --create-home --uid 1000 ccproxy \
    && mkdir -p /app/data \
    && chown -R ccproxy:ccproxy /app
USER ccproxy

# declare the data dir as a volume so `docker run` without an explicit mount
# still persists to an anonymous volume rather than the container layer
VOLUME ["/app/data"]

EXPOSE 8181

# /health returns 200 as soon as the server answers (no key needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, requests; requests.get('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8181'), timeout=4).raise_for_status()"

CMD ["python", "ccproxy.py"]
