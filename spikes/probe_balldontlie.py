"""THROWAWAY spike: measure what the BALLDONTLIE free tier actually gives us.

Not production code. No error handling worth the name, prints instead of
returning. The deliverable is the findings we write into DECISIONS.md,
not this script.

Usage:
    python spikes/probe_balldontlie.py              # shape probe only
    python spikes/probe_balldontlie.py --ratelimit  # also measure the 429 limit
"""

import json
import os
import pathlib
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ.get("BALLDONTLIE_API_KEY")
if not KEY:
    sys.exit("No BALLDONTLIE_API_KEY. Copy .env.example to .env and add your key.")

# The playbook says /nba/v1; other sources say /v1. Measure, don't guess.
BASE_CANDIDATES = ["https://api.balldontlie.io/nba/v1", "https://api.balldontlie.io/v1"]
# Docs disagree on raw-key vs Bearer. Try both.
AUTH_SCHEMES = [lambda k: k, lambda k: f"Bearer {k}"]
SAMPLES = pathlib.Path(__file__).parent / "samples"


def get(base, scheme, path, **params):
    return requests.get(
        f"{base}/{path}",
        headers={"Authorization": scheme(KEY)},
        params=params,
        timeout=15,
    )


def discover():
    """Find the base URL + auth scheme combination that actually authenticates."""
    for base in BASE_CANDIDATES:
        for i, scheme in enumerate(AUTH_SCHEMES):
            try:
                r = get(base, scheme, "teams", per_page=1)
            except requests.RequestException as e:
                print(f"  {base:42} [{i}] network error: {e}")
                continue
            print(f"  {base:42} [{'raw' if i == 0 else 'Bearer'}] -> {r.status_code}")
            if r.status_code == 200:
                return base, scheme
    sys.exit("No base URL + auth scheme combination returned 200. Check the key.")


def probe(base, scheme, path, **params):
    """Record status, top-level shape, and one sample record for an endpoint."""
    r = get(base, scheme, path, **params)
    print(f"\n=== /{path} -> {r.status_code} {'OK' if r.ok else r.reason}")
    if not r.ok:
        print(f"    body: {r.text[:200]}")
        return
    body = r.json()
    print(f"    top-level keys: {list(body)}")
    print(f"    meta: {body.get('meta')}")
    records = body.get("data") or []
    if isinstance(records, list) and records:
        print(f"    {len(records)} record(s); first record fields:")
        for k, v in records[0].items():
            kind = type(v).__name__
            preview = json.dumps(v)[:60] if isinstance(v, dict) else repr(v)[:60]
            print(f"      {k:22} {kind:6} {preview}")
    SAMPLES.mkdir(exist_ok=True)
    (SAMPLES / f"{path.replace('/', '_')}.json").write_text(json.dumps(body, indent=2))


def measure_rate_limit(base, scheme, cap=30):
    """Fire requests until a 429. You cannot cache around a limit you never measured."""
    print(f"\n=== rate limit: firing up to {cap} requests until 429")
    start = time.monotonic()
    for n in range(1, cap + 1):
        r = get(base, scheme, "teams", per_page=1)
        if r.status_code == 429:
            print(f"    429 on request #{n} after {time.monotonic() - start:.1f}s")
            print(f"    headers: {dict(r.headers)}")
            return
        print(f"    #{n:>2} {r.status_code}", end="\r")
    print(f"\n    no 429 in {cap} requests over {time.monotonic() - start:.1f}s")


print("Discovering base URL + auth scheme...")
base, scheme = discover()
print(f"\nUSING: {base}\n")

# Named so we can probe ONE endpoint and not spend quota re-fetching known shapes.
PROBES = {
    "teams": {},
    "players": {"per_page": 2},
    "games": {"per_page": 2, "seasons[]": 2024},
    "standings": {"season": 2024},
}
wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or list(PROBES)
for name in wanted:
    probe(base, scheme, name, **PROBES[name])

if "--ratelimit" in sys.argv:
    measure_rate_limit(base, scheme)
else:
    print("\n(skipping rate-limit test; re-run with --ratelimit)")
