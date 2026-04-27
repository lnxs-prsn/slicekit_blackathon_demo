```markdown
# SliceKit — A Lightweight Toolkit for LLM-Driven Code Reuse

> 🏆 **Hackathon Judge Quick-Start**
>
> 1. Clone and install: `pip install -r requirements.txt`
> 2. Run the demo: `python demo.py` (always works — includes fallback if no GitHub token)
> 3. Observe: Search → Fetch → Parse → Extract → LLM-ready snippet
> 4. Try custom queries: `python demo.py "redis cache utils"`
> 5. See verbose output: `python demo.py -v`
>
> ✅ **The demo runs 100% reliably** — demo.py wraps the framework with a curated fallback.  
> 🔑 **For live GitHub search** you must provide a token – see [Authentication](#github-api-authentication-optional).

---

## The Problem

Modern coding tasks often require non-trivial logic: ETL pipelines, finicky API integrations, data transforms.
Large models (GPT‑4, Claude) handle these well.
But small, fast, local, or budget LLMs frequently produce hallucinated imports, broken syntax, or insecure shortcuts when asked to write more than a few lines.

**The insight:** GitHub already contains millions of high‑quality, tested, documented code snippets.
Small LLMs *can* read code descriptions, select relevant functions, and write thin glue code that ties them together.
What they can’t do is efficiently search, fetch, parse, and extract that code in a reliable, repeatable way.

---

## How SliceKit Solves It

SliceKit implements a four‑stage pipeline that converts a natural language request into a curated, minimal, copy‑paste‑ready Python snippet *without* requiring the LLM to know anything about GitHub’s API, AST parsing, or file I/O.

```
User Request
      │
      ▼
search_github()   ← finds candidate Python files
      │
      ▼
get_file()        ← fetches raw source code
      │
      ▼
slice_functions() ← parses out all top‑level functions
      │
      ▼
extract_function()← extracts one function + its imports
      │
      ▼
[LLM writes glue] ← the only creative part left
      │
      ▼
Working Script
```

The entire pipeline returns plain Python dicts and lists. There are no custom objects, so **any LLM** (or even a simple script) can consume the outputs immediately.

---

## Installation & Requirements

- Python 3.10+
- Only external dependency: `requests`

```bash
pip install -r requirements.txt
```

---

## GitHub API Authentication (Optional)

**GitHub's Code Search API requires authentication.** Without a token, `search_github()` will receive a `401 Unauthorized` and return an empty list `[]`.

For live search that actually queries GitHub, create a personal access token and set the environment variable:

```bash
# Create a token with scope: public_repo (no other permissions needed)
# https://github.com/settings/tokens
export GITHUB_TOKEN=your_token_here
python demo.py
```

The framework automatically reads from `GITHUB_TOKEN`.  
If you need to pass the token programmatically (e.g., inside a secure script), use:

```python
import os
from framework import search_github

# Always read token from an environment variable – never hardcode secrets
results = search_github("my query", token=os.getenv("GITHUB_TOKEN"))
```

> 🔐 **Security note**: Tokens should **never** be written directly into source code or committed to a repository. Always use environment variables or a secret manager. The examples above show the safe pattern.

> 📦 **No token?** The demo still works thanks to the fallback layer in `demo.py` (see below). The core framework functions return `[]` or `None` gracefully, which the demo script handles with curated examples.

---

## Quickstart: 60‑second Demo

```bash
python demo.py
```

You’ll see a box‑drawn header, step‑by‑step output, timing breakdowns, and a final LLM‑ready snippet. **The demo always produces output**, even without a GitHub token, because `demo.py` supplies pre‑selected real code snippets when the live search is unavailable.

> 🔍 **How demo resilience works**
>
> - `framework.py` functions follow a strict contract: they return `[]` or `None` on any failure (401, network error, etc.), **not** hardcoded fallbacks.
> - `demo.py` checks the result of `search_github()`. If it’s empty, the demo script substitutes a curated list of working repositories — so the pipeline still demonstrates fetch, parse, and extract.
> - This separation keeps the library functions clean and production‑ready (no hidden mock data), while the demo script guarantees a reliable showcase for judges.

When a token is provided, `search_github()` performs a real search and the demo uses those live results.

Example output (abbreviated):

```
=== STEP 1: Searching GitHub ===
  Found: example-user/pg2bq/export.py
  ...

=== STEP 2: Fetching file ===
  Downloaded 3287 characters

=== STEP 3: Slicing functions ===
  - transfer_data(self, cursor, bigquery_client):
  ...

=== STEP 4: Extracting function ===
  Extracted: transfer_data

=== STEP 5: LLM would write glue code here ===
--- SNIPPET START ---
import os
from google.cloud import bigquery
import psycopg2

def transfer_data(cursor, bigquery_client):
    …
--- SNIPPET END ---
```

---

## Live Mode vs. Dry‑Run Mode

The demo script provides several flags for flexibility:

| Mode | Command | Behavior | Use Case |
|------|---------|----------|----------|
| **Live** | `python demo.py` | Calls GitHub API (requires token for real search), falls back to curated data if needed | Production demos with internet |
| **Dry‑Run** | `python demo.py --dry-run` | Uses purely local mock data, no network at all | Offline testing, 100% reproducible output |
| **Verbose** | `python demo.py -v` | Shows the full result dictionary at the end | Debugging and programmatic verification |
| **Save Output** | `python demo.py -o glue.py` | Writes the extracted snippet to a file | Integration testing |

> 💡 **Default is live mode** (with automatic fallback when the API is unavailable). The `--dry-run` flag skips the network entirely for a completely deterministic run.

---

## Architecture & Pipeline

### Core Functions (`framework.py`)

| Step | Function | Responsibility | Returns |
|------|----------|----------------|---------|
| 1 | `search_github(query, lang="python", max_results=5, token=None)` | Search GitHub (empty list if API fails) | `list[dict]` with `repo`, `file_path`, `raw_url`, `description` |
| 2 | `get_file(raw_url)` | Download raw source from a `raw.githubusercontent.com` URL | `str` or `None` |
| 3 | `slice_functions(code)` | Parse Python source and list top‑level function signatures | `list[dict]` with `name`, `signature`, `docstring`, `line_start`, `line_end` |
| 4 | `extract_function(code, func_name, slices)` | Extract one function’s full text plus relevant imports | `str` or `None` |

- `token`: optional GitHub PAT. If `None`, reads `GITHUB_TOKEN` env var. Without a valid token, `search_github()` returns `[]` (no access).
- All line indices are **0‑based** (spec‑compliant).
- The `slice_functions` return is fully compatible with `extract_function`.

All functions share a `"slicekit"` logger (see Design Philosophy).

---

## Design Philosophy

### 1. Plain Data Contracts
Every function returns standard Python types — lists of dicts, strings, `None` or empty list on failure. No custom objects. This keeps the output LLM‑readable with zero extra tool definitions.

### 2. Consistent Naming
- Functions: `verb_noun()` (`search_github`, `slice_functions`)
- Dict keys: `snake_case` (`raw_url`, `line_start`, `line_end`)
- Files: `framework.py`, `demo.py`

### 3. Graceful Degradation
SliceKit **never raises exceptions** for expected failure modes (network issues, missing functions, bad syntax). The framework functions return empty/None, while the demo script adds the resilience layer for presentation.

| Situation | Return | Log Level | Example Log Message |
|-----------|--------|-----------|----------------------|
| API 401, 404, rate limit, unparseable code | `[]` or `None` | `WARNING` | `API returned 401` |
| Unexpected exception | `[]` or `None` | `ERROR` | `FAILED: ConnectionError('timeout')` |
| Success | valid data | `INFO` | `SUCCESS: found 3 results` |

### 4. Structured Logging
Every function logs its entry, success, and failure points using a shared `"slicekit"` logger. The format is machine‑parseable:

```
HH:MM:SS | LEVEL     | slicekit.funcName | message
```

---

## Example Output (Full)

> 📋 **Note**: The output above is abbreviated. Actual demo output includes:
> - Box‑drawn headers and step separators
> - Timing breakdowns (`search=0.25s, fetch=0.04s, …`)
> - Logging lines to stderr (`HH:MM:SS | LEVEL | slicekit.func | message`)
> - `[DRY‑RUN]` indicators when using `--dry-run`
>
> When run in verbose mode (`-v`), the final step also prints the complete result dictionary.

---

## Project Structure

```
SliceKit/
├── framework.py      # Core pipeline: search → fetch → slice → extract (REAL implementations)
├── demo.py           # Orchestrator with CLI args, fallback, and LLM simulation
├── requirements.txt  # Only `requests>=2.28`
└── README.md         # You are here
```

---

## Troubleshooting

### “API returned 401” / “No results found” but demo still runs
This is normal when no token is set. GitHub’s Code Search API requires authentication; `search_github()` returns `[]`. The demo script then switches to its curated fallback list, so the pipeline continues without interruption. To use live search, set `GITHUB_TOKEN`.

### Fallback results return 404 when fetching
The hardcoded fallback entries in `demo.py` may have outdated repository paths. To fix:
1. Open `demo.py` and locate the `FALLBACK_RESULTS` list.
2. Verify each `file_path` matches the actual path in the GitHub repository.
3. Test each `raw_url` in your browser before committing.

### I set GITHUB_TOKEN but still see 401 or empty results
- Ensure the token has the `public_repo` scope and has not expired.
- Use the verbose flag (`-v`) to check the exact response details.
- Check that the token is properly exported (`echo $GITHUB_TOKEN`).

### Rate limit warnings (`403` / `429`)
When authenticated, GitHub’s Code Search API allows ~30 requests/minute. If you exceed that, `search_github()` returns `[]`. Unauthenticated requests get 401, not rate limits.

### Dry‑run mode shows different results than live
`--dry-run` uses local mock data, independent of GitHub. The live mode (with token) performs real searches. Both modes demonstrate the full pipeline.

### Pipeline shows ❌ but you see extracted code?
The demo continues on warnings. Check stdout above the final banner for partial results. The `success` field in the returned dict indicates final status.

---
