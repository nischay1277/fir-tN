.PHONY: install dev api web build serve

install:
	uv sync --extra full
	cd frontend && npm install

dev:
	./start.sh

api:
	uv run --extra full uvicorn fir.serving.app:app --reload --host 127.0.0.1 --port 8000

web:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

serve: build
	uv run --extra full uvicorn fir.serving.app:app --host 127.0.0.1 --port 8000
