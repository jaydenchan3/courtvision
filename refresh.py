"""Refresh the API-cache tables from BALLDONTLIE.

Run out of band -- never from a request. The free tier is 5 requests/minute,
so this is a manual or scheduled step, and the app serves SQLite regardless of
whether it has ever succeeded.

    python refresh.py

Exits non-zero on failure so a scheduler can notice, but never with a
traceback: a failed refresh is an expected outcome, not a crash.
"""

import sys

from app.data import models, nba_api


def main():
    conn = models.get_connection()
    result = nba_api.refresh_cache(conn)

    if not result.ok:
        print(f"Refresh failed ({result.kind}): {result.reason}")
        print("Existing cached data is unchanged; the app continues to serve it.")
        return 1

    print(f"Refreshed {models.DB_PATH}")
    for resource, count in result.written.items():
        skipped = result.skipped.get(resource, 0)
        note = f"  ({skipped} skipped: unknown team)" if skipped else ""
        print(f"  {resource:9} {count} rows{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
