all: fmt mypy test

fmt:
	ruff format *.py
	ruff check *.py

mypy:
	mypy --install-types --non-interactive --ignore-missing-imports *.py

test:
	python3 -m unittest

setup-dicts:
	uv run python -m wn download oewn:2024
	uv run python -m wn download omw-fr
	uv run python -m wn download omw-en:2.0

