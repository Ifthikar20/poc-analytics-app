PORT ?= 8000

.PHONY: setup build run dev test

## Install everything (python venv + node modules)
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.txt
	npm --prefix frontend install

## Build the React dashboard into frontend/dist (served by FastAPI)
build:
	npm --prefix frontend run build

## One-command demo: build the dashboard, start the backend on :$(PORT)
run: build
	.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $(PORT)

## Two-process dev mode: uvicorn --reload on :8000 + Vite HMR on :5173
dev:
	bash scripts/dev.sh

test:
	cd backend && ../.venv/bin/pytest -q
