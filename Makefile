all: fmt mypy test

fmt:
	ruff format *.py
	ruff check *.py

mypy:
	mypy --install-types --non-interactive --ignore-missing-imports *.py

test:
	python3 -m unittest
