# AGENTS.md

## Project Overview

**udsbot** is a Telegram bot implemented from scratch (no bot framework) for learning purposes, built for the **PyMI** (Vietnamese Python community). It provides a wide range of utilities: dictionary lookups (English, French, Japanese), weather and air quality data, cryptocurrency prices and charts, Japanese language learning tools (kanji quizzes, Jisho dictionary, Nikkei podcast), LLM-powered features (jokes, translations, example sentences), Advent of Code leaderboards, and a user-managed cron job scheduler. The bot is hosted on Telegram as [@pymi_udsbot](https://t.me/pymi_udsbot).

## Tech Stack

| Component        | Technology                                                        |
| ---------------- | ----------------------------------------------------------------- |
| Language         | Python 3.12+                                                      |
| HTTP Client      | `requests` (synchronous)                                          |
| Bot Architecture | Raw Telegram Bot API polling (no framework)                       |
| LLM (local)      | Ollama (`gemma3:1b` at `localhost:11434`)                         |
| LLM (cloud)      | OpenRouter API (default model: `google/gemma-4-31b-it:free`)      |
| Dictionary       | WordNet (`wn`) + `english-to-ipa` (fully offline)              |
| Japanese         | Jisho.org API + in-memory SQLite kanji database                   |
| Charting         | `pandas` + `plotly` (lazy-imported for crypto candlestick charts) |
| Config           | `PyYAML` + `Pydantic` (for cronjob storage config validation)     |
| Linter/Formatter | `ruff`                                                            |
| Type Checker     | `mypy`                                                            |
| Testing          | `unittest` (standard library)                                     |
| CI               | GitHub Actions (via `uv`)                                         |

## Architecture

```
bot.py                  ← Entry point: infinite polling loop (60s cycle), dispatches commands
├── config.py           ← BOT_TOKEN, TELEGRAM_BASE_URL, OFFSET_FILE constants
├── config.yaml         ← Cronjob storage backend config (SQL or JSON)
├── commands.py         ← Dispatcher class (dynamic dispatch via getattr) + all command handlers
│   ├── jp_dict.py      ← Jisho.org API client + in-memory SQLite kanji DB + KanjiService
│   ├── jp_podcast.py   ← Nagara Nikkei podcast episode scraper (Apple Podcasts)
│   ├── llm.py          ← Dual LLM backends: local Ollama + OpenRouter API
│   ├── joyo_final.json ← Full Jōyō kanji dataset (~564KB, 2136 kanji by grade)
│   ├── kanji.json      ← Sample Jisho API response (reference/documentation)
│   └── message.json    ← Sample Telegram update message (reference/documentation)
├── cronjob.py          ← Cron job scheduler with pluggable storage (Strategy pattern)
│   └── cronjob_config.py ← Pydantic models for storage config validation
└── test_cronjob.py     ← Comprehensive unittest tests for cron job module
```

The project uses a **flat module structure** — all Python files live at the repository root with no sub-packages.

## How the Bot Works

1. **`bot.py`** runs an infinite loop that polls Telegram's `getUpdates` API every 60 seconds.
2. The last processed `update_id` is persisted in `/tmp/uds_telegrambot_offset` to avoid reprocessing.
3. Messages older than 5 minutes are skipped.
4. Text messages are passed to `Dispatcher.dispatch()`, which uses **dynamic dispatch via `getattr`**: it strips the leading `/` from the command, looks up `dispatch_{cmd}` on the `Dispatcher` class, and calls it.
5. After processing messages, `cronjob.run_cron()` is called to execute any due scheduled jobs.
6. On dispatch errors, the traceback is sent back to the chat.

## Key Files

| File                | Purpose                                                                    |
| ------------------- | -------------------------------------------------------------------------- |
| `bot.py`            | Entry point. Polling loop, message fetching, dispatch orchestration.       |
| `commands.py`       | `Dispatcher` class with all `dispatch_*` command handlers + utility funcs. |
| `config.py`         | Constants: `BOT_TOKEN`, `TELEGRAM_BASE_URL`, `OFFSET_FILE`.               |
| `config.yaml`       | Cronjob storage backend configuration (SQL vs JSON).                       |
| `cronjob.py`        | Cron job scheduler with ABC `Storage` + `SQLStorage`/`JSONStorage`.        |
| `cronjob_config.py` | Pydantic models for type-safe config validation (discriminated union).     |
| `jp_dict.py`        | Jisho.org API client, `KanjiService`, in-memory SQLite kanji DB.          |
| `jp_podcast.py`     | Scrapes Apple Podcasts for Nagara Nikkei episodes.                         |
| `llm.py`            | Dual LLM integration: local Ollama + OpenRouter API.                       |
| `joyo_final.json`   | Complete Jōyō kanji dataset (2136 kanji organized by grade 1–8).          |
| `kanji.json`        | Sample Jisho API response structure (reference).                           |
| `message.json`      | Sample Telegram update message structure (reference).                      |
| `test_cronjob.py`   | Comprehensive tests for cronjob parsing, storage backends, and logic.      |

## Bot Commands

| Command               | Handler Method      | Description                                              |
| --------------------- | ------------------- | -------------------------------------------------------- |
| `/uds <word>`         | `dispatch_uds`      | Urban Dictionary lookup                                  |
| `/cam <word>`         | `dispatch_cam`      | Cambridge Dictionary (English) with IPA                  |
| `/fr <word>`          | `dispatch_fr`       | French WordNet (WOLF) lookup                             |
| `/ji <word>`          | `dispatch_ji`       | Jisho.org Japanese dictionary lookup                     |
| `/jo [grade] [nth]`   | `dispatch_jo`       | Random/specific Jōyō kanji by grade level                |
| `/hi`                 | `dispatch_hi`       | Weather + AQI for HCM, Hanoi, Singapore                  |
| `/tem`                | `dispatch_tem`      | Temperature only for HCM, Hanoi, Singapore               |
| `/aqi`                | `dispatch_aqi`      | Air Quality Index for HCM, Hanoi, Singapore              |
| `/btc [coin]`         | `dispatch_btc`      | Cryptocurrency price via CoinGecko                       |
| `/c [coin]`           | `dispatch_c`        | Cryptocurrency candlestick chart (60 days)               |
| `/aoc [topn]`         | `dispatch_aoc`      | Advent of Code 2024 private leaderboard                  |
| `/jk`                 | `dispatch_jk`       | Generate a joke via local Ollama LLM                     |
| `/lt <word>`          | `dispatch_lt`       | Define/translate a word via local Ollama LLM             |
| `/nikkei`             | `dispatch_nikkei`   | Latest Nikkei podcast episode + LLM translation          |
| `/x [cmd] [word]`     | `dispatch_x`        | Tatoeba example sentences (default), or `/x ai <word>` for LLM generation (supports reply) |
| `/cron HH:MM <cmd>`   | `dispatch_cron`     | Add a scheduled cron job                                 |
| `/delcron <UUID>`     | `dispatch_delcron`  | Delete a cron job by UUID                                |
| `/listcron`           | `dispatch_listcron` | List user's cron jobs                                    |

## Code Conventions

### Style

- **Synchronous**: The bot uses synchronous `requests` — not async. All handlers and API calls are regular functions.
- **Dynamic dispatch**: Adding a new command requires only adding a `dispatch_<name>` method on the `Dispatcher` class. No registration step needed.
- **Type hints**: Used throughout with `mypy` type checking enforced in CI.
- **Dataclasses**: Used for structured data (`Kanji`, `Job`, `PodcastEpisode`).
- **Pydantic**: Used for config validation in `cronjob_config.py` (discriminated unions).
- **Design patterns**: Strategy pattern (ABC + concrete implementations) for pluggable cron storage.
- **Logging**: Standard `logging` module used consistently.
- **Linting**: `ruff` for formatting and linting.

### Configuration & Secrets

- **Cronjob config** goes in `config.yaml` (storage backend selection: SQL or JSON).
- **Secrets** are loaded from environment variables — never committed to the repo.
- `config.py` exposes `BOT_TOKEN`, `TELEGRAM_BASE_URL`, and `OFFSET_FILE` as module-level constants.
- `commands.py` also reads `WEATHER_TOKEN` and `AOC_SESSION` directly from environment.
- `llm.py` reads `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from environment.

### Command Handlers

Each command is a method on the `Dispatcher` class with the signature:

```python
def dispatch_<name>(self, text: str, chat_id: int, from_id: int) -> None:
```

The `dispatch()` method routes incoming text to the appropriate handler via `getattr(self, f"dispatch_{pure_cmd}", print)`. Unknown commands fall through to `print` (stdout, not sent to user).

### Cron Job System

The cron subsystem uses a **Strategy pattern** with an abstract `Storage` base class:
- `SQLStorage` — SQLite implementation (`cronjobs.db`)
- `JSONStorage` — JSON file implementation (`cronjobs.json`)

The backend is selected at import time based on `config.yaml`. Jobs are limited to `MAX_JOBS_PER_OWNER = 10`. Management commands (`cron`, `addcron`, `delcron`, `listcron`) are excluded from scheduled execution to prevent recursion.

### LLM Integration

Two backends serve different purposes:
- **Ollama (local)**: `gemma3:1b` model at `localhost:11434` — used for jokes (`/jk`) and word definitions (`/lt`). Requires a running Ollama instance.
- **OpenRouter (cloud)**: Dynamic multi-model fallback list with `openrouter/free` router (default: `google/gemma-4-31b-it:free`, `liquid/lfm-2.5-2.6b:free`, `google/gemma-4-26b-a4b-it:free`, `minimax/minimax-m3:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `minimax/minimax-m2.7:free`, followed by `openrouter/free` router fallback) — used for Japanese translation (`/nikkei`) and example sentence generation (`/x ai`). OpenAI-compatible chat completions API.

### Module-Level Side Effects

Be aware of initialization that happens at import time:
- `commands.py` sets `os.environ["TZ"] = "Asia/Ho_Chi_Minh"` and initializes an in-memory SQLite kanji database.
- `cronjob.py` reads `config.yaml` and instantiates the storage backend.
- `llm.py` creates a persistent `requests.Session()` and reads API keys from environment.

## Testing

- **Framework**: `unittest` (standard library), **not pytest**.
- **Test files**: `test_cronjob.py`, `test_llm.py`, `test_commands.py`, `test_dict_lookup.py`, `test_jp_dict.py`.
- **Coverage includes**: Job parsing, storage backends, LLM fallback & chat completions, command dispatching, dictionary lookups, Jisho and Kanji parsing.
- **Mocking**: Uses `unittest.mock.patch` and `MagicMock` for external network/API requests and storage.
- **Run tests**: `make test` (which runs `python3 -m unittest`).

## Build & Run

```bash
# Install dependencies
uv sync

# Run all quality checks (format + type check + test)
make all

# Download offline WordNet lexicons (required for /cam and /fr)
make setup-dicts

# Individual targets
make fmt          # ruff format *.py && ruff check *.py
make mypy         # mypy --install-types --non-interactive --ignore-missing-imports *.py
make test         # python3 -m unittest
make audit        # uvx detect-secrets + gitleaks (optional) + uvx pip-audit + uvx semgrep

# Run the bot
python bot.py
```

## CI/CD

- **GitHub Actions** workflow (`python-quality-checks.yml`) runs on push/PR to `main`/`master`.
- Steps: checkout → Python 3.12 setup → `uv sync` → `uv run make fmt` → `uv run make mypy` → `uv run make test`.
- Runs on `ubuntu-latest`.

## Environment Variables

| Variable        | Required | Used In        | Description                                  |
| --------------- | -------- | -------------- | -------------------------------------------- |
| `BOT_TOKEN`     | Yes      | `config.py`, `commands.py` | Telegram Bot API token              |
| `WEATHER_TOKEN` | Yes      | `commands.py`  | OpenWeatherMap API key                       |
| `OPENROUTER_API_KEY` | No      | `llm.py`       | OpenRouter API key (required for /x ai, /nikkei) |
| `OPENROUTER_MODEL`  | No       | `llm.py`       | OpenRouter model or comma-separated fallback list (default: `google/gemma-4-31b-it:free,liquid/lfm-2.5-2.6b:free,google/gemma-4-26b-a4b-it:free,minimax/minimax-m3:free,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,minimax/minimax-m2.7:free`) |
| `AOC_SESSION`   | No       | `commands.py`  | Advent of Code session cookie                |

## External Dependencies

| Dependency | Source | Purpose |
| ---------- | ------ | ------- |
| `wn` | PyPI | Open English WordNet and French WOLF dictionary lookup |
| `english-to-ipa` | GitHub | Converting English text to IPA pronunciation offline |
| `requests` | PyPI | HTTP client for all API calls |
| `pydantic` | PyPI | Config validation for cronjob storage |
| `pyyaml` | PyPI | YAML config loading |
| `pandas` | PyPI | Crypto chart data processing (lazy-imported) |
| `plotly` | PyPI | Candlestick chart generation (lazy-imported) |
| `lxml[html-clean]` | PyPI | HTML parsing |
| `matplotlib` | PyPI | Plotting support |
| `numpy` | PyPI | Numerical operations |


## Runtime Requirements

- **Ollama** must be running locally at `localhost:11434` with the `gemma3:1b` model for `/jk` and `/lt` commands.
- State files: `/tmp/uds_telegrambot_offset` (update offset), `cronjobs.db` or `cronjobs.json` (cron storage), `.secrets.baseline` (detect-secrets baseline).
- Internet access for Telegram API, OpenWeatherMap, CoinGecko, WAQI, Jisho.org, Apple Podcasts, OpenRouter.

## Guidelines for AI Agents

1. **Flat structure**: Keep all Python modules at the repo root. Do not introduce sub-packages without explicit approval.
2. **Synchronous code**: The bot uses synchronous `requests`. Do not introduce async/await unless migrating the entire codebase.
3. **Dynamic dispatch**: To add a new command `/foo`, add a `dispatch_foo` method on the `Dispatcher` class in `commands.py`. No registration needed.
4. **No secrets in code**: Never hardcode API keys or tokens. Use environment variables and reference them via `os.environ`.
5. **Test new features**: Add tests following the `test_<module>.py` convention using `unittest`. Mock external dependencies.
6. **Data files**: Large static datasets (like `joyo_final.json`) are stored as JSON at the repo root.
7. **Ruff compliance**: All code must pass `ruff format` and `ruff check`.
8. **mypy compliance**: All code must pass `mypy --ignore-missing-imports`.
9. **Python 3.12+**: Use modern Python features. Target `requires-python = ">=3.12"`.
10. **Dependencies**: Add new dependencies to `pyproject.toml`. The `uds` library is sourced from git via `[tool.uv.sources]`.
11. **Ollama dependency**: Features using local Ollama should gracefully handle connection failures.
12. **Lazy imports**: Heavy libraries (`pandas`, `plotly`) are lazy-imported inside functions to keep startup fast.
13. **Security audit must run make audit**: When performing security audits, always execute `make audit` (which runs `detect-secrets` against `.secrets.baseline` and `pip-audit`), scan `pyproject.toml` / `uv.lock` for vulnerability/deprecation risks, and grep for lazy imports of undeclared packages.

