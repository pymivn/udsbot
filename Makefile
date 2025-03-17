fmt:
	ruff format *.py
	ruff check *.py

mypy:
	mypy --ignore-missing-import *.py