"""
SliceKit Demo — End-to-end pipeline demonstration

Orchestrates the full SliceKit pipeline:
    search_github() → get_file() → slice_functions() → extract_function() → [LLM glue]

Usage:
    python demo.py                              # default query
    python demo.py "csv to json parser"         # custom query
    python demo.py "redis client" -n 5 -f get   # 5 results, extract 'get' function
    python demo.py "http utils" -f missing --fallback-first  # fallback to first if not found
    python demo.py "postgres etl" -v            # verbose: show result dict at end
    python demo.py --dry-run                    # offline mode with cached responses
    python demo.py "etl" -o glue.py             # save glue code to file
"""

import logging
import sys
import time

# ─── Logging Setup ───────────────────────────────────────────────────────────
# Use shared logger per contract
logger = logging.getLogger("slicekit")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)  # logs go to stderr
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ─── Dry-Run Mock Data ───────────────────────────────────────────────────────

_MOCK_SEARCH_RESULTS = [
    {
        "repo": "dataops/postgres-etl",
        "file_path": "pipeline/transfer.py",
        "raw_url": "https://raw.githubusercontent.com/dataops/postgres-etl/main/pipeline/transfer.py",
        "score": 42.5
    },
    {
        "repo": "analytics/bigquery-sync",
        "file_path": "src/sync.py",
        "raw_url": "https://raw.githubusercontent.com/analytics/bigquery-sync/main/src/sync.py",
        "score": 38.1
    },
    {
        "repo": "infra/etl-toolkit",
        "file_path": "lib/pg_bq.py",
        "raw_url": "https://raw.githubusercontent.com/infra/etl-toolkit/main/lib/pg_bq.py",
        "score": 31.7
    },
]

_MOCK_SOURCE_CODE = '''"""PostgreSQL to BigQuery ETL pipeline."""

import psycopg2
from google.cloud import bigquery


def get_pg_connection(config):
    """Create a PostgreSQL connection from config dict."""
    conn = psycopg2.connect(
        host=config["pg_host"],
        port=config.get("pg_port", 5432),
        database=config["pg_database"],
        user=config["pg_user"],
        password=config["pg_password"],
    )
    return conn


def extract_table(conn, table_name, batch_size=10000):
    """Extract rows from PostgreSQL table in batches."""
    cursor = conn.cursor(name="extract_cursor")
    cursor.itersize = batch_size
    cursor.execute(f"SELECT * FROM {table_name}")
    
    batches = []
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        batches.append(rows)
    
    cursor.close()
    return batches


def transform_rows(rows, column_map):
    """Apply column mapping and type conversions."""
    transformed = []
    for row in rows:
        mapped = {}
        for src_col, dst_col in column_map.items():
            value = row[src_col] if src_col in row else None
            mapped[dst_col] = str(value) if value is not None else None
        transformed.append(mapped)
    return transformed


def load_to_bigquery(client, dataset, table, rows):
    """Load transformed rows into BigQuery table."""
    if not rows:
        return {"inserted": 0}
    
    table_ref = client.dataset(dataset).table(table)
    errors = client.insert_rows_json(table_ref, rows)
    
    if errors:
        return {"inserted": 0, "errors": errors}
    return {"inserted": len(rows)}


def run_pipeline(config, table_name, column_map):
    """Execute full ETL: extract, transform, load."""
    conn = get_pg_connection(config)
    try:
        batches = extract_table(conn, table_name)
        bq_client = bigquery.Client()
        total = 0
        
        for batch in batches:
            transformed = transform_rows(batch, column_map)
            result = load_to_bigquery(bq_client, config["bq_dataset"], table_name, transformed)
            total += result["inserted"]
        
        return {"status": "success", "rows_inserted": total}
    finally:
        conn.close()
'''


# ─── Dry-Run Mock Functions ──────────────────────────────────────────────────

def _mock_search_github(query, max_results=3):
    """Return cached search results without network call."""
    time.sleep(0.05)  # simulate minimal latency
    return _MOCK_SEARCH_RESULTS[:max_results]


def _mock_get_file(raw_url):
    """Return cached source code without network call."""
    time.sleep(0.08)  # simulate minimal latency
    return _MOCK_SOURCE_CODE


# ─── Pipeline Orchestrator ───────────────────────────────────────────────────

def run_pipeline(
    query: str,
    max_results: int = 3,
    target_function: str | None=None,
    fallback_first: bool = False,
    verbose: bool = False,
    dry_run: bool = False,
    output_path: str | None=None
) -> dict:
    """
    Execute the full SliceKit pipeline and return results.
    
    Args:
        query: GitHub search query
        max_results: Max search results to fetch
        target_function: Specific function name to extract (None = first found)
        fallback_first: If True and target_function not found, use first function
        verbose: If True, include full metadata in output
        dry_run: If True, use cached responses instead of network calls
        output_path: If set, save glue code to this file path
    
    Returns:
        dict with keys: 'success', 'snippet', 'function_name', 'metadata', 'glue_code'
    """
    from framework import slice_functions, extract_function

    # Import real or mock functions based on dry_run
    if dry_run:
        search_fn = _mock_search_github
        get_fn = _mock_get_file
        logger.info("DRY_RUN: using cached responses (no network)")
    else:
        from framework import search_github, get_file
        search_fn = search_github
        get_fn = get_file

    # Timing
    pipeline_start = time.time()
    timings = {}

    result = {
        "success": False,
        "snippet": None,
        "function_name": None,
        "glue_code": None,
        "metadata": {"dry_run": dry_run}
    }

    # ═══ STEP 1: Search ═══════════════════════════════════════════════════
    print("\n" + "─" * 60)
    print("STEP 1: Searching GitHub")
    print("─" * 60)

    if dry_run:
        print("  [DRY-RUN] Using cached search results")

    logger.info(f"START: query='{query}', max_results={max_results}")
    step_start = time.time()

    search_results = search_fn(query, max_results=max_results)

    timings["search"] = time.time() - step_start

    if not search_results:
        logger.warning("No search results found, returning fallback")
        print("  ⚠ No results found. Try a different query.")
        result["metadata"]["timings"] = timings
        result["metadata"]["total_duration"] = time.time() - pipeline_start
        return result

    logger.info(f"SUCCESS: found {len(search_results)} results")
    result["metadata"]["search_count"] = len(search_results)

    for i, r in enumerate(search_results):
        print(f"  [{i + 1}] {r['repo']}/{r['file_path']}")
        if "score" in r:
            print(f"      relevance: {r['score']}")

    # ═══ STEP 2: Fetch ════════════════════════════════════════════════════
    print("\n" + "─" * 60)
    print("STEP 2: Fetching file")
    print("─" * 60)

    selected = search_results[0]
    raw_url = selected["raw_url"]

    if dry_run:
        print("  [DRY-RUN] Using cached file content")

    logger.info(f"START: url={raw_url}")
    print(f"  Source: {selected['repo']}/{selected['file_path']}")
    step_start = time.time()

    code = get_fn(raw_url)

    timings["fetch"] = time.time() - step_start

    if not code:
        logger.warning("Failed to fetch file content")
        print("  ⚠ Could not download file.")
        result["metadata"]["timings"] = timings
        result["metadata"]["total_duration"] = time.time() - pipeline_start
        return result

    line_count = len(code.splitlines())
    logger.info(f"SUCCESS: {len(code)} chars, {line_count} lines")
    print(f"  Downloaded: {len(code)} chars, {line_count} lines")

    result["metadata"]["file_size"] = len(code)
    result["metadata"]["file_lines"] = line_count

    # ═══ STEP 3: Slice ════════════════════════════════════════════════════
    print("\n" + "─" * 60)
    print("STEP 3: Slicing functions")
    print("─" * 60)

    logger.info("START: parsing functions from source")
    step_start = time.time()

    functions = slice_functions(code)

    timings["slice"] = time.time() - step_start

    if not functions:
        logger.warning("No functions found in file")
        print("  ⚠ No parseable functions found.")
        result["metadata"]["timings"] = timings
        result["metadata"]["total_duration"] = time.time() - pipeline_start
        return result

    logger.info(f"SUCCESS: found {len(functions)} functions")
    print(f"  Found {len(functions)} function(s):")

    for i, f in enumerate(functions):
        signature = f["signature"].replace("def ", "")
        lines = f["line_end"] - f["line_start"] + 1
        print(f"    [{i + 1}] {f['name']}{signature}")
        print(f"        lines {f['line_start']}-{f['line_end']} ({lines} lines)")

    result["metadata"]["functions_found"] = len(functions)
    result["metadata"]["function_names"] = [f["name"] for f in functions]

    # ═══ STEP 4: Extract ══════════════════════════════════════════════════
    print("\n" + "─" * 60)
    print("STEP 4: Extracting function")
    print("─" * 60)

    # Determine target function
    if target_function:
        found = any(f["name"] == target_function for f in functions)
        if not found:
            if fallback_first:
                extract_name = functions[0]["name"]
                logger.warning(
                    f"Function '{target_function}' not found, falling back to '{extract_name}'"
                )
                print(f"  ⚠ '{target_function}' not found, using '{extract_name}' (--fallback-first)")
            else:
                logger.warning(f"Function '{target_function}' not found in sliced list")
                print(f"  ⚠ Function '{target_function}' not found.")
                print(f"  Available: {[f['name'] for f in functions]}")
                print(f"  Hint: add --fallback-first to auto-select first function")
                result["metadata"]["timings"] = timings
                result["metadata"]["total_duration"] = time.time() - pipeline_start
                return result
        else:
            extract_name = target_function
            print(f"  Target: {extract_name} (user-specified)")
    else:
        extract_name = functions[0]["name"]
        print(f"  Target: {extract_name} (auto-selected)")

    logger.info(f"START: extracting '{extract_name}'")
    step_start = time.time()

    snippet = extract_function(code, extract_name, functions)

    timings["extract"] = time.time() - step_start

    if not snippet:
        logger.error(f"FAILED: could not extract '{extract_name}'")
        print(f"  ⚠ Extraction failed.")
        result["metadata"]["timings"] = timings
        result["metadata"]["total_duration"] = time.time() - pipeline_start
        return result

    snippet_lines = len(snippet.splitlines())
    logger.info(f"SUCCESS: extracted {snippet_lines} lines")
    print(f"  Extracted: {snippet_lines} lines")

    result["success"] = True
    result["snippet"] = snippet
    result["function_name"] = extract_name
    result["metadata"]["snippet_lines"] = snippet_lines

    # ═══ STEP 5: LLM Glue (Simulated) ════════════════════════════════════
    print("\n" + "─" * 60)
    print("STEP 5: LLM glue code generation (simulated)")
    print("─" * 60)
    print()
    print("  At this point, SliceKit hands off to the LLM:")
    print("    • Input: extracted function snippet")
    print("    • Task: write minimal glue code to integrate it")
    print("    • Output: working script")
    print()

    # Find the function info for signature
    func_info = next((f for f in functions if f["name"] == extract_name), None)

    print("┌── EXTRACTED SNIPPET ──────────────────────────────────────")
    for line in snippet.splitlines():
        print(f"│ {line}")
    print("└───────────────────────────────────────────────────────────")
    print()

    step_start = time.time()
    glue_code = _simulate_llm_glue(extract_name, snippet, func_info)
    timings["glue"] = time.time() - step_start

    print("┌── GENERATED GLUE CODE (LLM output) ──────────────────────")
    for line in glue_code.splitlines():
        print(f"│ {line}")
    print("└───────────────────────────────────────────────────────────")

    result["glue_code"] = glue_code

    # ═══ Save Output ══════════════════════════════════════════════════════
    if output_path:
        try:
            with open(output_path, "w") as f:
                f.write(glue_code)
            logger.info(f"SUCCESS: glue code saved to {output_path}")
            print(f"\n  💾 Glue code saved to: {output_path}")
            result["metadata"]["output_file"] = output_path
        except OSError as e:
            logger.error(f"FAILED: could not write to {output_path}: {e}")
            print(f"\n  ⚠ Could not save to {output_path}: {e}")

    # ═══ Timing Summary ═══════════════════════════════════════════════════
    timings["total"] = time.time() - pipeline_start
    result["metadata"]["timings"] = timings

    logger.info(f"PIPELINE_DURATION: {timings['total']:.2f}s")
    logger.info(
        f"TIMING_BREAKDOWN: search={timings['search']:.2f}s, "
        f"fetch={timings['fetch']:.2f}s, "
        f"slice={timings['slice']:.2f}s, "
        f"extract={timings['extract']:.2f}s, "
        f"glue={timings['glue']:.2f}s"
    )

    # ═══ Verbose Output ═══════════════════════════════════════════════════
    if verbose:
        print("\n" + "─" * 60)
        print("RESULT DICT (verbose)")
        print("─" * 60)
        # Print without snippet/glue_code to keep output manageable
        verbose_result = {
            k: v for k, v in result.items()
            if k not in ("snippet", "glue_code")
        }
        verbose_result["snippet_lines"] = result["metadata"].get("snippet_lines")
        for line in _format_dict(verbose_result).splitlines():
            print(f"  {line}")

    return result


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _format_dict(d: dict, indent: int = 0) -> str:
    """Format a dict for readable printing."""
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_format_dict(v, indent + 1))
        elif isinstance(v, list) and len(v) <= 5:
            lines.append(f"{prefix}{k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{prefix}{k}: [{v[0]}, ...] ({len(v)} items)")
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)


def _simulate_llm_glue(func_name: str, snippet: str, func_info: dict|None) -> str:
    """
    Simulate what a small LLM would generate as glue code.
    
    In production, this would be an actual LLM call. Here we show
    the pattern: the LLM receives the snippet and writes integration code.
    """
    if not func_info:
        signature = f"{func_name}(...)"
    else:
        signature = func_info["signature"].replace("def ", "").rstrip(":")

    # Build a realistic glue template
    lines = [
        f"# Glue code generated to integrate: {func_name}",
        f"# Original signature: {signature}",
        "",
        "import json",
        "import sys",
        "",
        "# ── Extracted function (from SliceKit) ──",
        "",
        snippet,
        "",
        "# ── Integration code (LLM-written) ──",
        "",
        "def main():",
        f'    """Use {func_name} in a real workflow."""',
        "    # TODO: Parse inputs from CLI, env, or config",
        '    # inputs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}',
        "",
        "    # TODO: Call the extracted function",
        f"    # result = {func_name}(**inputs)",
        "",
        "    # TODO: Handle output",
        '    # print(json.dumps(result, default=str))',
        f'    print("Integration point for {func_name}")',
        "",
        'if __name__ == "__main__":',
        "    main()",
    ]

    return "\n".join(lines)


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    """Demo entry point with CLI argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SliceKit Demo — LLM-driven code reuse pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py                              # default: "postgres to bigquery etl"
  python demo.py "csv parser python"          # custom search query
  python demo.py "redis client" -n 5          # fetch up to 5 results
  python demo.py "http utils" -f get_headers  # extract specific function
  python demo.py "http utils" -f missing --fallback-first  # fallback if not found
  python demo.py "postgres etl" -v            # verbose: show result dict
  python demo.py --dry-run                    # offline mode with cached responses
  python demo.py "etl" -o glue.py             # save glue code to file
  python demo.py --dry-run -o out.py -v       # offline + save + verbose
        """
    )

    parser.add_argument(
        "query",
        nargs="?",
        default="postgres to bigquery etl",
        help="GitHub search query (default: 'postgres to bigquery etl')"
    )
    parser.add_argument(
        "-n", "--max-results",
        type=int,
        default=3,
        metavar="N",
        help="maximum search results to retrieve (default: 3)"
    )
    parser.add_argument(
        "-f", "--function",
        default=None,
        metavar="NAME",
        help="specific function name to extract (default: first found)"
    )
    parser.add_argument(
        "--fallback-first",
        action="store_true",
        help="if -f target not found, extract first function instead of failing"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show full result dict at end for programmatic verification"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="skip network calls, use cached responses for offline testing"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="FILE",
        help="save generated glue code to FILE"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="suppress logging output"
    )

    args = parser.parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    # Banner
    dry_label = " [DRY-RUN]" if args.dry_run else ""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                       SliceKit Demo                        ║")
    print("║            LLM-driven code reuse pipeline                  ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Query: {args.query[:47]:<47}║")
    print(f"║  Max results: {args.max_results:<41}║")
    print(f"║  Target func: {(args.function or 'auto'):<42}║")
    print(f"║  Fallback:    {'yes' if args.fallback_first else 'no':<42}║")
    print(f"║  Output:      {(args.output or 'stdout'):<42}║")
    print(f"║  Mode:        {'dry-run' if args.dry_run else 'live':<42}║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Run pipeline
    result = run_pipeline(
        query=args.query,
        max_results=args.max_results,
        target_function=args.function,
        fallback_first=args.fallback_first,
        verbose=args.verbose,
        dry_run=args.dry_run,
        output_path=args.output
    )

    # Final status
    print("\n" + "═" * 60)
    if result["success"]:
        duration = result["metadata"].get("timings", {}).get("total", 0)
        print(f"✅ Pipeline complete — snippet ready for use ({duration:.2f}s)")
        logger.info(
            f"PIPELINE_SUCCESS: {result['function_name']}, "
            f"{result['metadata']['snippet_lines']} lines, "
            f"{duration:.2f}s"
        )
    else:
        print("❌ Pipeline incomplete — see warnings above")
        logger.warning("PIPELINE_FAILED")
    print("═" * 60)
    print()

    # Return exit code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()