all: fmt mypy

fmt:
	ruff format *.py
	ruff check *.py

mypy:
	mypy --install-types --non-interactive --ignore-missing-imports *.py
