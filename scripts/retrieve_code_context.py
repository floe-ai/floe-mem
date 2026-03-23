#!/usr/bin/env python3
"""Deprecated: code context is returned through memory.search/build_context_bundle."""
import json

if __name__ == "__main__":
    print(json.dumps({
        "ok": False,
        "error": "retrieve_code_context is superseded by memory.search and memory.build_context_bundle"
    }))
    raise SystemExit(1)
