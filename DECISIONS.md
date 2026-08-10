# Design decisions

One entry per real decision: what was chosen, what was rejected, and why.
This is the file to re-read before an interview.

---

## Why a public API, not scraping

Scraping goes against many rules, public API also 

---

## Why injuries/stats are seeded at MVP

They are viable for the MVP and adds features that make it stand out.

---

## API spike findings — BALLDONTLIE, measured 2026-08-09

Measured with real calls (`spikes/probe_balldontlie.py`), not read from docs.
Raw responses saved in `spikes/samples/` so the schema can be designed without
spending quota.

| Question | Measured answer |
| --- | --- |
| Base URL | `https://api.balldontlie.io/nba/v1` (the bare `/v1` variant never answered) |
| Auth | Raw key in the `Authorization` header — **no** `Bearer` prefix |
| Rate limit | **5 requests / minute.** `x-ratelimit-limit: 5`, `retry-after: 59` on the 429 |
| `/teams` | 200 — 45 records, unpaginated, includes defunct franchises |
| `/players` | 200 — cursor pagination (`meta.next_cursor`); `team` is a nested object |
| `/games` | 200 — cursor pagination; 30+ fields; `home_team`/`visitor_team` nested |
| `/standings` | **401 — not included in the free tier** |

**`/standings` is excluded from the MVP.** The 401 persisted while sibling
endpoints were returning 429 on the same key, which isolates it to tier gating
rather than a bad key or a bad parameter. Any standings feature is dropped now,
before a UI is built on top of it.

**5 req/min makes the SQLite cache mandatory, not an optimization.** The API
cannot sit in the page-load path: a single user clicking between three pages
would exhaust the window. This is the reason for the cache, and it is a stronger
justification than "caching is faster."

**Nested team objects become foreign keys.** `players.team`, `games.home_team`
and `games.visitor_team` all arrive as full nested objects. Flattening a team
name into a text column on every row would denormalize 45 teams across every
player and turn "who plays for OKC" into a string match. Store `team_id` and
join locally — cheap, because `/teams` is one unpaginated call cached once.

**Cache only the fields the product uses.** `/games` returns quarter scores,
three overtime slots, timeouts remaining, and In-Season Tournament stage. None
of it answers the product's questions. Every cached column is one more thing to
keep correct and migrate.

**`datetime` is UTC and `date` is not.** A game at `2024-10-22T23:30:00.000Z` is
Oct 22 evening in the US; a 02:00Z tip-off belongs to the *previous* local
evening. "Who plays tonight?" is the headline feature, so the local-date
boundary is decided deliberately in the schema, not by accident.

**Graceful degradation.** Because reads come from SQLite and never from a live
call, an API outage or an exhausted quota degrades the app to serving the last
cached data rather than erroring. Combined with seeded injuries/stats, the app
and the entire E2E suite run with no network at all.

---

<!--
Entries still to come, per the build plan:
  - Caching strategy (why SQLite, not per-request API calls)
  - Graceful degradation when the data source is unavailable
  - Explicit-wait approach
  - Locator strategy
  - Page Object Model boundary
  - Test isolation and data strategy
  - CI readiness check
  - Test-plan technique mapping
-->
