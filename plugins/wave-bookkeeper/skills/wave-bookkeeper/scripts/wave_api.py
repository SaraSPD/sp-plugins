#!/usr/bin/env python3
"""Minimal GraphQL client for Wave's public API.

Reads the token from wave-token.txt in the project root (the directory
you run wave_push.py from). Keep that file out of version control --
it's a live credential.
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

# Project root = wherever the user is running these scripts from.
# wave-token.txt, wave-ids.json, and the month folders all live here.
HERE = Path.cwd()

ENDPOINT = "https://gql.waveapps.com/graphql/public"


def _token():
    token_file = HERE / "wave-token.txt"
    if not token_file.exists():
        raise SystemExit(
            f"ABORT: {token_file} not found. See references/wave-api-setup.md "
            "for how to generate a Wave API token."
        )
    return token_file.read_text().strip()


def gql_raw(query, variables=None):
    """Run a raw GraphQL query/mutation against Wave. Returns the parsed JSON body
    (which may contain a top-level 'errors' array even on HTTP 200 -- callers should
    check that, not just rely on this not raising)."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"errors": [{"message": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}"}]}
