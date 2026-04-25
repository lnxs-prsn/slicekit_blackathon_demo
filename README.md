
**README.md**
```markdown
# SliceKit — A Lightweight Toolkit for LLM-Driven Code Reuse

**SliceKit** gives small, inexpensive language models a deterministic mechanical layer for code discovery, retrieval, parsing, and extraction. Instead of asking a tiny LLM to generate complex code from scratch, you let it **curate and glue** existing, battle-tested code — SliceKit handles the plumbing.

---

## The Problem

Modern coding tasks often require non-trivial logic: ETL pipelines, finicky API integrations, data transforms. Large models (GPT-4, Claude) handle these well. But small, fast, local, or budget LLMs frequently produce hallucinated imports, broken syntax, or insecure shortcuts when asked to write more than a few lines.

**The insight:** GitHub already contains millions of high-quality, tested, documented code snippets. Small LLMs *can* read code descriptions, select relevant functions, and write thin glue code that ties them together. What they can’t do is efficiently search, fetch, parse, and extract that code in a reliable, repeatable way.

---

## How SliceKit Solves It

SliceKit implements a four-stage pipeline that converts a natural language request into a curated, minimal, copy‑paste‑ready Python snippet *without* requiring the LLM to know anything about GitHub’s API, AST parsing, or file I/O.

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

That’s it.

---

## Quickstart: 60-second Demo

The demo (`demo.py`) runs an end‑to‑end example that searches for PostgreSQL‑to‑BigQuery ETL code, fetches it, lists the functions inside, extracts one, and prints it out ready for an LLM to glue.

```bash
python demo.py
```

You’ll see:

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

That snippet is now in the perfect shape for an LLM to reason about and write minimal surrounding glue (argument construction, config loading, error handling).

---

## Architecture & Pipeline

### Core Functions (`framework.py`)

| Step | Function | Responsibility | Returns |
|------|----------|----------------|---------|
| 1 | `search_github(query, lang, max_results)` | Search public GitHub for Python files | `list[dict]` with keys `repo`, `file_path`, `raw_url`, `description` |
| 2 | `get_file(raw_url)` | Download raw source from a `raw.githubusercontent.com` URL | `str` or `None` |
| 3 | `slice_functions(code)` | Parse Python source and list all top‑level function signatures | `list[dict]` with `name`, `signature`, `docstring`, `line_start`, `line_end` |
| 4 | `extract_function(code, func_name, slices)` | Extract one function’s full text plus relevant imports | `str` or `None` |

All functions share a `"slicekit"` logger, following a strict logging contract (see below).

### Demo Orchestrator (`demo.py`)

- Chains the four functions in order
- Simulates the LLM’s “pick and glue” step (just prints the extracted snippet)
- Shows exactly what a real agent loop would receive

---

## Design Philosophy

### 1. Plain Data Contracts

Every function returns standard Python types:
- Lists of dictionaries
- Strings
- `None` or empty list on failure

No classes, no custom objects. This means:
- LLMs can reason about returned data without custom tool definitions
- Humans can inspect results with a simple `print()`
- No coupling between modules

### 2. Consistent Naming

- Functions: `verb_noun()` (`search_github`, `slice_functions`)
- Dict keys: `snake_case` (`raw_url`, `line_start`, `line_end`)
- Files: `framework.py`, `demo.py`

### 3. Graceful Degradation

SliceKit **never raises exceptions for expected failure modes** (network issues, missing functions, bad syntax).

| Situation | Return | Log Level | Example Log Message |
|-----------|--------|-----------|----------------------|
| Rate limit, 404, unparseable code | `[]` or `None` | `WARNING` | `API rate limit hit, returning fallback` |
| Unexpected exception | `[]` or `None` | `ERROR` | `FAILED: ConnectionError('timeout')` |
| Success | valid data | `INFO` | `SUCCESS: found 3 results` |

This makes the pipeline **demo‑resilient** — even if GitHub is flaky, the demo still runs (falling back to a hardcoded example when necessary).

### 4. Structured Logging

Every function logs its entry, success, and failure points using a shared `"slicekit"` logger. The format is machine‑parseable:

```
HH:MM:SS | LEVEL     | slicekit.funcName | message
```

This is consistent across all modules, making debugging transparent during a live demo.

---

## Project Structure

```
SliceKit/
├── framework.py      # Core pipeline functions (search → fetch → slice → extract)
├── demo.py           # End‑to‑end demo orchestrator (simulates LLM glue step)
├── requirements.txt  # Only `requests`
└── README.md         # You are here
```

---

## Example Output

When `demo.py` runs against a real GitHub file:

```
=== Extracted Snippet ===
import logging
from sqlalchemy import create_engine

def transfer_data(source_conn_str, dest_conn_str, query):
    """Stream data from source to destination."""
    source_engine = create_engine(source_conn_str)
    dest_engine = create_engine(dest_conn_str)
    with source_engine.connect() as src, dest_engine.connect() as dst:
        result = src.execute(query)
        for row in result:
            dst.execute("INSERT INTO ... VALUES (...)", row)
```
*An LLM now only needs to write: argument parsing, chunking, and error handling.*

---

## Future Improvements

- **Caching layer:** Cache fetched files to speed repeated searches
- **Multi‑language support:** Extend `lang` parameter to JavaScript, Go, etc.
- **Smarter import extraction:** Resolve which imports are actually used in the extracted function
- **Claude/GPT integration:** Add a real LLM‑based glue writer module (Section E is a placeholder for that)

---

## License

```

**requirements.txt**
```
requests>=2.28
```
