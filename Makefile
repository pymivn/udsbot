all: fmt ty test

fmt:
	ruff format *.py
	ruff check *.py

ty:
	uvx ty check *.py

test:
	python3 -m unittest

audit:
	uvx --from detect-secrets detect-secrets-hook --baseline .secrets.baseline $$(git ls-files)
	@if command -v gitleaks >/dev/null 2>&1; then gitleaks git -v; fi
	uvx pip-audit
	uvx semgrep scan --config p/python --config p/secrets --quiet



setup-dicts:
	uv run python -m wn download oewn:2024
	uv run python -m wn download omw-fr
	uv run python -m wn download omw-en:2.0

enrich-kanji:
	uv run python jp_dict.py --enrich --limit 50


