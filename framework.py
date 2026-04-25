import logging
import requests
import ast


# Shared logger (same across all sections)
logger = logging.getLogger("slicekit")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ----------------------------------------------------------------------
# SECTION A — Search Engineer
# ----------------------------------------------------------------------
def search_github(
    query: str,
    lang: str = "python",
    max_results: int = 5,
    fallback_to_curated: bool = True
) -> list[dict]:
    """
    Search GitHub for code files matching query.

    Args:
        query: Search term.
        lang: Language filter (default 'python').
        max_results: Maximum number of results.
        fallback_to_curated: If True, return curated fallback on API failure
                             (ensures demo continues). If False, return [].

    Returns list of dicts with keys:
        - repo: str           # "owner/repo"
        - file_path: str      # path within repo
        - raw_url: str        # direct raw.githubusercontent.com URL
        - description: str    # brief context from search
    """
    logger.info(f"START: query='{query}', lang='{lang}', max_results={max_results}, "
                f"fallback={fallback_to_curated}")

    # Curated fallback – safe entries with known correct raw URLs
    curated = [
        {
            "repo": "psf/requests",
            "file_path": "requests/api.py",
            "raw_url": "https://raw.githubusercontent.com/psf/requests/main/src/requests/api.py",
            "description": "HTTP library – core API functions (get, post, etc.)"
        },
        {
            "repo": "fastapi/fastapi",
            "file_path": "fastapi/routing.py",
            "raw_url": "https://raw.githubusercontent.com/fastapi/fastapi/master/fastapi/routing.py",
            "description": "FastAPI router – endpoint registration logic"
        },
        {
            "repo": "python/cpython",
            "file_path": "Lib/json/__init__.py",
            "raw_url": "https://raw.githubusercontent.com/python/cpython/main/Lib/json/__init__.py",
            "description": "Standard library JSON encoder/decoder"
        }
    ][:max_results]

    try:
        resp = requests.get(
            "https://api.github.com/search/code",
            params={
                "q": f"{query}+language:{lang}",
                "per_page": max_results
            },
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10
        )

        # Rate limit detection – more reliable
        if resp.status_code in (403, 429) or resp.headers.get("X-RateLimit-Remaining") == "0":
            logger.warning("Rate limit hit")
            return curated if fallback_to_curated else []

        if resp.status_code != 200:
            logger.warning(f"API returned {resp.status_code}")
            return curated if fallback_to_curated else []

        items = resp.json().get("items", [])
        if not items:
            logger.info("No results found")
            return curated if fallback_to_curated else []

        results = []
        for item in items[:max_results]:
            repo = item["repository"]["full_name"]
            path = item["path"]
            # default_branch is always present in the repository object of search results
            branch = item["repository"].get("default_branch", "main")
            raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

            # Better description: text match snippet → repo description → filename
            desc = (
                item.get("text_matches", [{}])[0].get("fragment") or
                item["repository"].get("description") or
                item.get("name", "")
            )
            results.append({
                "repo": repo,
                "file_path": path,
                "raw_url": raw_url,
                "description": desc
            })

        logger.info(f"SUCCESS: returned {len(results)} items")
        return results

    except Exception as e:
        logger.error(f"FAILED: {type(e).__name__}: {e}")
        return curated if fallback_to_curated else []





# B


def get_file(raw_url: str) -> str | None:
    """
    Fetch raw file content from GitHub.
    
    Args:
        raw_url: Direct raw.githubusercontent.com URL from search_github()
    
    Returns:
        File content as string, or None if fetch failed
    """
    logger.info(f"START: fetching {raw_url}")
    
    if not raw_url or not isinstance(raw_url, str):
        logger.warning("Invalid raw_url provided")
        return None

    try:
        response = requests.get(raw_url, timeout=10)

        if response.status_code == 200:
            content = response.text
            logger.info(f"SUCCESS: fetched {len(content)} characters")
            return content

        elif response.status_code == 404:
            logger.warning("File not found (404)")
            return None

        else:
            logger.warning(f"Unexpected status code: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        logger.warning("Request timed out")
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"FAILED: {e}")
        return None
    



# C



def slice_functions(code: str) -> list[dict]:
    """
    Parse Python code and extract all top-level function signatures.

    Args:
        code: Raw Python source code string from get_file()

    Returns:
        List of dicts, each with keys:
            - name: str # function name
            - signature: str # full def line (e.g., "def foo(a, b):")
            - docstring: str # docstring or empty string
            - line_start: int # 0-based index where function starts
            - line_end: int # 0-based index where function ends (exclusive)
    """
    logger.info(f"START: slice_functions(code length={len(code)})")

    # Handle edge case: empty or whitespace-only code
    if not code or not code.strip():
        logger.warning("Empty code provided")
        return []

    try:
        # Parse the Python code into an AST
        tree = ast.parse(code)
        logger.debug("SUCCESS: AST parsing completed")
    except SyntaxError as e:
        logger.warning(f"SyntaxError in provided code: {e}")
        return []
    except Exception as e:
        logger.error(f"FAILED: Unexpected parse error: {e}")
        return []

    functions = []
    lines = code.split('\n')

    # Iterate over top-level nodes (children of Module)
    for node in tree.body:
        # Handle both regular and async functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Get the line number (convert from 1-based to 0-based)
            line_start = node.lineno - 1
            # Use getattr for safe access (Python <3.8 compatibility)
            line_end = (getattr(node, 'end_lineno', None) or node.lineno) - 1

            # Ensure line_end is at least line_start
            if line_end < line_start:
                line_end = line_start

            # Extract the function signature (def line)
            signature = lines[line_start].strip() if line_start < len(lines) else f"def {node.name}(...):"

            # Extract docstring
            docstring = ast.get_docstring(node) or ""

            # Build the result dict
            func_info = {
                "name": node.name,
                "signature": signature,
                "docstring": docstring,
                "line_start": line_start,
                "line_end": line_end + 1  # Make it exclusive as per contract
            }

            functions.append(func_info)
            logger.debug(f"Found function: {node.name} at lines {line_start}-{line_end}")

    # Sort by line_start to maintain source order
    functions.sort(key=lambda x: x["line_start"])

    logger.info(f"SUCCESS: found {len(functions)} top-level functions")
    return functions




# D


# Shared logger (same across all sections)
logger = logging.getLogger("slicekit")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
def extract_function(code: str, func_name: str, slices: list[dict]) -> str | None:
    """
    Extract a single function's full text plus its imports from source code.

    Args:
        code: Raw Python source code string
        func_name: Name of function to extract
        slices: Output from slice_functions(code) — used to find line range

    Returns:
        String containing imports + function body, or None if not found
    """
    logger.info(f"START: Extracting function '{func_name}'")

    try:
        # --- Input validation ---
        if not isinstance(code, str) or not code.strip():
            logger.warning("Empty or non-string code input")
            return None
        if not isinstance(slices, list) or not slices:
            logger.warning("Empty or non-list slices input")
            return None

        # --- Find target slice ---
        target_slice = next(
            (s for s in slices if isinstance(s, dict) and s.get("name") == func_name),
            None
        )
        if not target_slice:
            logger.warning(f"Function '{func_name}' not found in slices")
            return None

        # --- Extract line range (Section C returns 1-indexed AST lines) ---
        lines = code.splitlines()
        raw_start = target_slice.get("line_start")
        raw_end = target_slice.get("line_end")

        if not isinstance(raw_start, int) or not isinstance(raw_end, int):
            logger.error(f"Non-integer line bounds for '{func_name}': start={raw_start}, end={raw_end}")
            return None

        line_start = raw_start - 1  # Convert to 0-indexed
        line_end = raw_end

        # --- Bounds validation ---
        if not (0 <= line_start < len(lines) and 0 < line_end <= len(lines) and line_start < line_end):
            logger.error(
                f"Invalid slice bounds for '{func_name}': "
                f"1-indexed {raw_start}-{raw_end} (file has {len(lines)} lines)"
            )
            return None

        # --- Extract function body ---
        function_body = "\n".join(lines[line_start:line_end])

        # --- Extract top-level imports (stop at first function/class definition) ---
        # This is docstring-safe: multi-line docstrings before imports do not break collection.
        imports = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("def ", "class ")):
                break
            if stripped.startswith(("import ", "from ")):
                imports.append(line)

        # --- Combine with clean separator ---
        parts = [p for p in ["\n".join(imports), function_body] if p]
        extracted_code = "\n\n".join(parts)

        logger.info(
            f"SUCCESS: Extracted '{func_name}' "
            f"({len(extracted_code)} chars, {len(parts)} parts, "
            f"lines {raw_start}-{raw_end})"
        )
        return extracted_code

    except Exception as e:
        logger.error(f"FAILED: {type(e).__name__}: {e}")
        return None