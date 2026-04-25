import logging
import sys
import time

from framework import slice_functions, extract_function, search_github, get_file

# ----------------------------------------------------------------------
# SECTION E — Demo (example usage, not part of core library)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Demo orchestration showing A → B → C → D pipeline
    
    print("=== STEP 1: Searching GitHub ===")
    results = search_github("postgres to bigquery etl", max_results=3)
    
    if not results:
        print("  No results found. Demo cannot continue.")
        # FIX: If you want curated fallback for demo purposes, do it HERE
        # in demo.py, not inside search_github(). This preserves the spec
        # contract while allowing demo resilience.
        print("  (For demo only: would use curated fallback here)")
    else:
        for r in results:
            print(f"  Found: {r['repo']}/{r['file_path']}")

        print("\n=== STEP 2: Fetching file ===")
        code = get_file(results[0]["raw_url"])
        if code is None:
            print("  Failed to fetch file.")
        else:
            print(f"  Downloaded {len(code)} characters")

            print("\n=== STEP 3: Slicing functions ===")
            functions = slice_functions(code)
            for f in functions:
                sig = f['signature'].replace('def ', '')
                print(f"  - {f['name']}{sig}")

            if functions:
                print("\n=== STEP 4: Extracting function ===")
                target = functions[0]["name"]
                snippet = extract_function(code, target, functions)
                print(f"  Extracted: {target}")

                print("\n=== STEP 5: LLM-ready snippet ===")
                print("--- SNIPPET START ---")
                print(snippet)
                print("--- SNIPPET END ---")