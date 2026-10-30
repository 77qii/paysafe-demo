#!/usr/bin/env bash
# Entry point for the hosted build.
#
# Streamlit has to bind the single public port and accept the reverse proxy in
# front of it, so the flags live here rather than in a one-line start command
# where the shell would mangle $PORT.
set -euo pipefail

export PAYSAFE_HOSTED=1

exec streamlit run app.py \
  --server.port "${PORT:-3000}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.fileWatcherType none \
  --browser.gatherUsageStats false
