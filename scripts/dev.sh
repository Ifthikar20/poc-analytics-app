#!/usr/bin/env bash
# Two-process dev mode: backend with hot reload + Vite dev server with HMR.
# The Vite dev server (http://localhost:5173) proxies /api, /demo and
# /tracker.js to the backend on :8000.
set -e
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT INT TERM
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000 &
npm --prefix frontend run dev &
wait
