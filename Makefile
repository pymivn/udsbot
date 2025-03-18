all: fmt mypy

fmt:
	ruff format *.py
	ruff check *.py

mypy:
	mypy --install-types --ignore-missing-import *.py
