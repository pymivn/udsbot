all: fmt mypy

fmt:
	ruff format *.py
	ruff check *.py

mypy:
	mypy --install-types
	mypy --ignore-missing-import *.py
