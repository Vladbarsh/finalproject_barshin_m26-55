.PHONY: install run lint format build check-package

install:
	uv sync --locked

run:
	uv run project

lint:
	uv run ruff check .

format:
	uv run ruff format --check .

build:
	uv build

check-package: build
	uvx twine check dist/*
