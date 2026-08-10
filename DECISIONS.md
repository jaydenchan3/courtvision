# Design decisions

One entry per real decision: what was chosen, what was rejected, and why.
This is the file to re-read before an interview.

---

## Why a public API, not scraping

**Chosen:** pull NBA data from the public BALLDONTLIE API.
**Rejected:** logging into ESPN/Yahoo Fantasy with Selenium and scraping my own
roster, which was the original idea for this project.

Three reasons.

1. **Terms of service.** ESPN and Yahoo both prohibit automated access to
   logged-in pages. Building a portfolio project on a documented ToS violation
   is indefensible on a public repo with my name on it.

2. **Fragility.** A scraper is coupled to someone else's HTML. Any redesign —
   which I don't control and get no warning about — breaks it silently. A
   versioned JSON API is a contract; a rendered page is not. Maintaining a
   scraper is unpaid work that would have consumed the time meant for the test
   suite, which is the actual point of this project.

3. **How it reads in an interview.** "I automated a site that forbids
   automation" invites doubt about my judgment. "I used the documented public
   API" invites no questions at all.

**The reframe that matters:** dropping the scraper costs no Selenium practice.
Every skill worth demonstrating — login flows, explicit waits, dynamic content,
tables, forms, the Page Object Model — is exercised against my own app instead.
That is also how Selenium is used professionally: as the end-to-end test layer
for your own product, not as an acquisition tool for someone else's data.

The personal-roster feature survives intact — the user enters their own players
manually, so nothing needs to touch anyone's fantasy account.

---

## Why injuries/stats are seeded at MVP

**Chosen:** injuries and per-player stats are fixed fixtures written by
`seed.py`. **Rejected:** fetching either one live.

1. **Determinism — the main reason.** End-to-end tests assert on what the user
   sees, so the data behind the screen has to be stable. A test asserting "the
   injury widget shows 3 players out" only means something if that number
   cannot change on its own. Live injury status changes hourly; a player is
   cleared to play and a green suite goes red without a line of code changing.
   That is a flaky failure, and flaky failures train a team to re-run instead
   of investigate, at which point the suite stops being a gate. Seeded data
   makes every assertion reproducible on any machine, on any day.

2. **The measured request budget makes it infeasible anyway.** The free tier
   allows 5 requests per minute (see the spike findings below). Assembling
   season averages for ~40 players would take dozens of calls and many minutes
   just to populate one page. The three endpoints verified as available —
   teams, players, games — carry no injury data at all, and `/standings`
   returning 401 already proved the free tier gates endpoints.

3. **A derived trend would move under the tests.** "Trending up" computed from
   recent games changes as games are played. Storing `trend` as a fixed value
   means the dashboard can render it and a test can assert on it.

4. **It keeps the whole suite offline.** No API key in CI, no quota, no 429, no
   network flake. The tests exercise the app, not the internet.

**Honest tradeoff:** at MVP the injury and trend data is realistic but not
real, so the app is a working demo of the interface rather than a live tool.
The upgrade path is narrow: swap the seeded source for a real feed and cache it
in the same tables, exactly like teams/players/games. Nothing above the data
layer changes, because Flask only ever reads SQLite.

This is also what makes the dashboard's headline features — who is out tonight,
who is trending — possible at all without a paid tier.

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
| `/teams` | 200 — 45 records, unpaginated: **30 current franchises + 15 defunct** |
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

**Only the 30 current teams are seeded, filtered on `division`.** `/teams`
returns 45 records: the 30 current NBA franchises plus 15 defunct ones (Chicago
Stags, Toronto Huskies, Sheboygan Redskins...). Two traps in that data:

- On defunct records `conference` is `'    '` — four spaces, not `''`. A
  whitespace string is truthy in Python, so `if team["conference"]` filters
  nothing. Filter on `division` (genuinely empty) or use `.strip()`.
- **"Denver Nuggets" appears twice**: id 8 is the current team, id 50 a defunct
  1949–50 franchise. Any lookup by `full_name` silently returns the wrong row.
  This is the concrete argument for keying on the API's `id`, never on a name.

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
