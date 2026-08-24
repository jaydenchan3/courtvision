# CourtVision

Full-stack fantasy basketball dashboard (Flask, SQLite, public NBA API) with a
Selenium + pytest end-to-end test suite running headless in CI.

![CI](https://github.com/jaydenchan3/courtvision/actions/workflows/ci.yml/badge.svg)

## What it is

Fantasy managers check several scattered sources every day — who plays tonight,
who's injured, who's trending, who's worth adding off waivers. CourtVision pulls
that into one dashboard so the daily decision takes a couple of minutes instead
of fifteen.

It exists for two reasons, and both matter equally: it's a real working app, and
it's the system under test for a professional-grade Selenium suite. Selenium is
used here the way it's used on the job — as the end-to-end test layer for my own
product, not as a scraper for someone else's site.

## The test suite

29 end-to-end tests across five areas, all driving a real headless Chrome.

| Area | Tests | What they cover |
| --- | --- | --- |
| `auth` | 7 | Valid/invalid login, protected-route redirect, `?next=` handling, logout |
| `dashboard` | 6 | Async load, spinner, seeded games and injuries, empty state |
| `roster` | 7 | Add, remove, duplicate rejection, the 13-player cap |
| `waiver` | 5 | Default sort, re-sorting, team filter, sort-key whitelist |
| `search` | 4 | Results, partial match, and two distinct empty states |

The decisions behind it, in short — the full reasoning is in
[DECISIONS.md](DECISIONS.md):

- **Explicit waits only.** No `time.sleep`, and no implicit wait is ever set —
  the two don't compose and mixing them produces unpredictable timeouts. The
  dashboard deliberately loads its data asynchronously behind a 400 ms delay, so
  the wait behaviour is exercised rather than assumed.
- **Page Object Model.** Locators are class-level `By` tuples on `id` /
  `data-testid` hooks — never CSS classes, never absolute XPath, never inline in
  a test. Page objects hold locators and actions; tests hold the assertions.
- **Real isolation.** Every test re-seeds the database *and* clears browser
  cookies. The suite runs against a throwaway SQLite file and never touches the
  development database. Tests pass in any order and on repeat runs.
- **Assertions import message constants** from the app instead of pasting text,
  so rewording a message doesn't fail a test that isn't about wording.

## Architecture

```
BALLDONTLIE API ──▶ spikes/samples/*.json ──▶ seed.py ──▶ SQLite
                                                            │
                                             app/data/queries.py  (all SQL)
                                                            │
                                             app/server.py  (routes, no SQL)
                                                            │
                                          HTML + JSON ──▶ Selenium suite
```

Flask only ever reads SQLite, never the API directly. That's not an
optimisation — the free tier is **5 requests per minute**, measured, so the API
cannot sit in the page-load path. It also means the app degrades gracefully:
if the data source is unavailable, it serves the last cached data instead of
erroring, and the entire suite runs with no network at all.

## Honest scope

**Injuries and player stats are seeded, not live.** The verified free-tier
endpoints (`/teams`, `/players`, `/games`) carry no injury data, `/standings`
and `/players/active` return 401, and a computed "trending" value would shift
daily and break assertions. Seeded data is what makes the E2E assertions stable,
which is the point of the project — but it does mean the injury and trend data
is realistic rather than real. Reasoning in
[DECISIONS.md](DECISIONS.md#why-injuriesstats-are-seeded-at-mvp).

Also deliberately out of scope at v1: multi-user auth, live refresh from the
API, cross-browser matrices, and parallel test execution.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env             # optional: only needed to re-run the API spike
python seed.py
python -m flask --app app:create_app run
```

Then open http://127.0.0.1:5000 and sign in with **demo** / **courtvision**.

## Run the tests

Requires Chrome. Selenium Manager fetches the matching driver automatically —
there's nothing to install or pin.

```bash
python -m pytest                      # the whole suite, headless
python -m pytest -m dashboard         # one area
python -m pytest tests/test_roster.py::test_roster_cap_is_enforced   # one test
```

Markers: `auth`, `dashboard`, `roster`, `waiver`, `search`.

## Layout

```
app/
  __init__.py     application factory, per-request DB connection, auth guard
  server.py       routes and error mapping — contains no SQL
  data/
    models.py     schema, connection handling, DB path override
    queries.py    every SQL statement in the application
  templates/      base, login, dashboard, roster, waiver, search
  static/         style.css, dashboard.js (the async load)
seed.py           deterministic offline seed
spikes/           throwaway API probe + saved sample responses
tests/
  conftest.py     live server, headless Chrome, per-test reseed fixtures
  pages/          Page Object Model
  test_*.py       the 29 end-to-end tests
```

## Tech

Python · Flask · SQLite · Selenium 4 · pytest · GitHub Actions
