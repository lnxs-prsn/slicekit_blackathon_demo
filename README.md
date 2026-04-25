You're absolutely right — the phrasing "higher rate limits" implies that there’s some level of access without a token, just at a lower rate. In reality, without a token GitHub’s `/search/code` endpoint returns **401** (no access at all), not a lower rate limit. SliceKit’s fallback is a hardcoded curated list, not degraded access. The documentation should make that distinction clear.

Below is the **final, corrected README.md** with all misleading phrasing removed. The token now enables **access** (with rate limits), and the fallback is explicitly presented as an alternative to that access, not a lower tier of the same service.

---

```markdown
# SliceKit — A Lightweight Toolkit for LLM-Driven Code Reuse

> 🏆 **Hackathon Judge Quick-Start**
>
> 1. Clone and install: `pip install -r requirements.txt`
> 2. Run the demo: `python demo.py` (live) or `python demo.py --dry-run` (offline)
> 3. Observe: Search → Fetch → Parse → Extract → LLM-ready snippet
> 4. Try custom queries: `python demo.py "redis cache utils"`
> 5. See verbose output: `python demo.py -v`
>
> ✅ The demo always works — fallback mode guarantees reliability even if GitHub’s API is unavailable.  
> 🔑 To access live GitHub search (the API requires authentication), set `GITHUB_TOKEN` as described below.

---

## The Problem

Modern coding tasks often require non-trivial logic: ETL pipelines, finicky API integrations, data transforms. Large models (GPT‑4, Claude) handle these well. But small, fast, local, or budget LLMs frequently produce hallucinated imports, broken syntax, or insecure shortcuts when asked to write more than a few lines.

**The insight:** GitHub already contains millions of high‑quality, tested, documented code snippets. Small LLMs *can* read code descriptions, select relevant functions, and write thin glue code that ties them together. What they can’t do is efficiently search, fetch, parse, and extract that code in a reliable, repeatable way.

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

SliceKit works **without any credentials** by using resilient fallback examples (curated, real code snippets). If you want live search that actually queries GitHub:

```bash
# Create a personal access token (scope: public_repo only)
# https://github.com/settings/tokens
export GITHUB_TOKEN=your_token_here
python demo.py
```

The `search_github()` function automatically reads `GITHUB_TOKEN` from the environment.  
If you need to pass the token programmatically (e.g., inside a secure script), use:

```python
import os
from framework import search_github

# Always read token from an environment variable – never hardcode it
results = search_github("my query", token=os.getenv("GITHUB_TOKEN"))
```

> 🔐 **Security note**: Tokens should **never** be written directly into source code or committed to a repository. Always use environment variables or a secret manager. The examples above show the safe pattern.

---

## Quickstart: 60‑second Demo

```bash
python demo.py
```

You’ll see a box‑drawn header, step‑by‑step output, timing breakdowns, and a final LLM‑ready snippet.

> 🔍 **About the Demo Search Results**
>
> GitHub’s Code Search API (`/search/code`) requires authentication. Without a token it returns **401 Unauthorized**.  
> When running `demo.py`:
> - SliceKit **gracefully falls back** to curated example files that are real, runnable Python snippets — just pre‑selected for reliability.
> - The query you see in the demo output is shown for context, but the results come from the fallback list.
> - To activate **live search** with your own queries, set `GITHUB_TOKEN` as shown above.
>
> **Why?** This fallback‑first design guarantees the demo **always works** for judges, while the architecture fully supports live search in production with proper authentication.

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

SliceKit is built for real GitHub integration, but the demo includes additional flags for reliability and testing:

| Mode | Command | Behavior | Use Case |
|------|---------|----------|----------|
| **Live** | `python demo.py` | Calls GitHub API (requires token for search), fetches real files | Production use, live demos with internet |
| **Dry‑Run** | `python demo.py --dry-run` | Uses cached mock data, no network | Offline testing, reproducible judge demos |
| **Verbose** | `python demo.py -v` | Shows full result dict at end | Debugging, programmatic verification |
| **Save Output** | `python demo.py -o glue.py` | Writes generated glue code to file | Integration testing |

> 💡 **Default is live mode**. The `--dry-run` flag is purely for convenience — the core `framework.py` functions always execute real logic when called directly (search falls back to curated list on 401).

---

## Architecture & Pipeline

### Core Functions (`framework.py`)

| Step | Function | Responsibility | Returns |
|------|----------|----------------|---------|
| 1 | `search_github(query, lang="python", max_results=5, fallback_to_curated=True, token=None)` | Search GitHub with auth + fallback support | `list[dict]` with `repo`, `file_path`, `raw_url`, `description` |
| 2 | `get_file(raw_url)` | Download raw source from a `raw.githubusercontent.com` URL | `str` or `None` |
| 3 | `slice_functions(code)` | Parse Python source and list all top‑level function signatures | `list[dict]` with `name`, `signature`, `docstring`, `line_start`, `line_end` |
| 4 | `extract_function(code, func_name, slices)` | Extract one function’s full text plus relevant imports | `str` or `None` |

> `token`: GitHub personal access token (optional). If `None`, reads `GITHUB_TOKEN` env var. Authenticated requests get access to live search with the standard rate limits (~30 req/min for code search).

All functions share a `"slicekit"` logger, following a strict logging contract (see Design Philosophy).

---

## Design Philosophy

### 1. Plain Data Contracts
Every function returns standard Python types — lists of dicts, strings, `None` or empty list on failure. No custom objects. This keeps the output LLM‑readable with zero extra tool definitions.

### 2. Consistent Naming
- Functions: `verb_noun()` (`search_github`, `slice_functions`)
- Dict keys: `snake_case` (`raw_url`, `line_start`, `line_end`)
- Files: `framework.py`, `demo.py`

### 3. Graceful Degradation
SliceKit **never raises exceptions** for expected failure modes (network issues, missing functions, bad syntax).

| Situation | Return | Log Level | Example Log Message |
|-----------|--------|-----------|----------------------|
| Rate limit, 404, unparseable code | `[]` or `None` | `WARNING` | `API rate limit hit, returning fallback` |
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
├── demo.py           # Orchestrator with CLI args + --dry-run mode + LLM simulation
├── requirements.txt  # Only `requests>=2.28`
└── README.md         # You are here
```

---

## Troubleshooting

### GitHub API returns 401 / Fallback mode activates
Without a token, GitHub’s Code Search API returns `401 Unauthorized`. SliceKit automatically falls back to curated examples. Set `GITHUB_TOKEN` to enable real search.

### Fallback results return 404 when fetching
The hardcoded fallback entries may point to outdated repository paths. To fix:
1. Edit `framework.py` and locate the `curated` list in `search_github()`
2. Verify `file_path` matches the actual path in the GitHub repo
3. Test the `raw_url` in your browser before committing

### Why does search show my query but return unrelated results?
In fallback mode, SliceKit uses high‑quality example repos to guarantee demo success. The query is logged for context, but results come from a curated list when the GitHub API is unavailable. This is intentional design for hackathon reliability.

### Rate limit warnings (`403` / `429`)
When authenticated, GitHub’s Code Search API allows ~30 requests/minute. If you exceed that, SliceKit will fall back to curated examples. For unauthenticated requests, the API returns 401, not a rate limit error.

### Dry‑run mode shows different results than live
`--dry-run` uses cached mock data for offline testing. Results are representative but not query‑specific. Use live mode for real GitHub results.

### Pipeline shows ❌ but you see extracted code?
The demo continues on warnings. Check stdout above the final banner for partial results. The `success` field in the returned dict indicates final status.

---

## Future Improvements

- **Caching layer:** Cache fetched files to speed repeated searches
- **Multi‑language support:** Extend `lang` parameter to JavaScript, Go, etc.
- **Smarter import extraction:** Resolve which imports are actually used in the extracted function
- **Real LLM integration:** Add a Claude/GPT‑based glue writer module (Section E is a placeholder for that)

---
