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
| `/players/active` | **401 — also not in the free tier** |

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

## Seed strategy and how determinism was proved

`seed.py` reads only from `spikes/samples/*.json`, so it runs with no network,
no API key and no quota. Seeded state: 30 teams, 40 players, 40 stat rows,
3 games dated today, 8 injuries, an 8-player starting roster (cap is 13, which
leaves room for the add/remove and boundary tests).

**Idempotency is verified, not assumed.** Counts matching across two runs
proves nothing, so the check hashes every row of every table and compares
fingerprints between consecutive runs. That check caught a real bug:

> `user_roster.id` was declared `INTEGER PRIMARY KEY AUTOINCREMENT`.
> `AUTOINCREMENT` makes SQLite record the highest id ever used in
> `sqlite_sequence`, and `DELETE FROM` does not reset it — so roster ids
> climbed (1–8, then 9–16, then 25–32) on every re-seed while the row *counts*
> stayed identical. Six of seven tables hashed the same; only this one drifted.
> Fixed by dropping `AUTOINCREMENT`: a plain `INTEGER PRIMARY KEY` restarts at
> 1 once the table is empty, and never-reuse semantics were never needed.

The lesson generalises: **a determinism claim needs a determinism test.** Any
test that later keys off a roster row id would have failed intermittently, and
the row counts would have said everything was fine.

**Player fixtures keep their real API ids.** The seed takes 40 players straight
from a saved `/players` page rather than inventing ids, which preserves the
natural-key invariant — a future live refresh upserts the same rows instead of
duplicating them.

**Known data-quality caveat.** The free-tier snapshot's team assignments are
stale or wrong in places (it lists Giannis Antetokounmpo on Miami). The seed
uses the API's values verbatim rather than hand-correcting them: corrections
would make the seed contradict its own source, would be overwritten by any
future refresh, and would mean maintaining a private patch list forever.

**Games are fixtures, not cached rows.** The 3 games use ids in a synthetic
900,001+ range so they can never collide with real BALLDONTLIE game ids, and
they are dated to the current US/Eastern date at seed time so "the dashboard
shows tonight's games" is assertable on any day the suite runs.

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

---

## The E2E test suite: isolation, waits, and locators

29 Selenium tests across five areas: auth (7), dashboard (6), roster (7),
waiver (5), search (4). Green twice in a row and green with the files run in
reverse order.

**Isolation has two halves, and forgetting the second one caused a real bug.**
The database is re-seeded before every test by an autouse fixture, so state
from one test cannot leak into the next. That alone was not enough: the driver
is session scoped, so its **cookies outlived each test**. A test that logged in
left the next one already authenticated, `/login` redirected instead of
rendering a form, and five auth tests failed in the suite while passing
individually. The fixture now clears cookies as well as re-seeding. The general
lesson: when a client is shared for speed, every piece of state it carries has
to be reset, not just the server's.

**Scope is chosen per cost.** Chrome and the HTTP server are session scoped
because launching a browser per test would dominate the runtime; the data is
function scoped because sharing it would make tests order-dependent. Share the
expensive thing, reset the state.

**No implicit wait is set anywhere, and there is no `time.sleep` in the
suite.** Implicit and explicit waits do not compose — mixing them produces
unpredictable, often much longer, timeouts. Every wait is a `WebDriverWait` on
a named `expected_condition`.

**The dashboard is deliberately asynchronous.** It serves a shell and fetches
its data behind a 400 ms server-side delay. `wait_loaded()` waits for *both*
the spinner becoming invisible and the content becoming visible, because
waiting on only one would pass against a half-rendered page. Form-post pages
wait on `staleness_of` the old DOM before reading the new one, which is what
stops a query from reading the pre-navigation page on a slow machine.

**Locators are `id` and `data-testid` only** — never CSS classes, never
absolute XPath, never written inline in a test. Classes exist for styling and a
restyle would break the suite for reasons unrelated to behaviour. Table rows
are addressed by `data-id`, not by index, because row position shifts as
players are added and removed.

**Message assertions import the constants from `app.server`** rather than
pasting the text, so rewording a message does not fail a test that is not about
wording — which is what trains a team to edit tests until they mean nothing.

**A zero-games state is reachable via `?date=`.** The empty-state test would
otherwise depend on the calendar, and a test that only passes on some days is a
test nobody trusts.

**One test bug worth recording.** The waiver sort assertion derived a surname
with `name.split()[-1]`, which returns `"III"` for "Marvin Bagley III". The app
was correct and the test was wrong. Verifying the failure rather than assuming
the app had broken is what separated the two.

---

## Three test layers, and why the pyramid is shaped this way

94 tests in three layers, each separately runnable:

| Layer | Count | Runtime | Scope |
| --- | --- | --- | --- |
| `unit` | 25 | **0.47 s** | One `queries.py` function, no HTTP, no browser |
| `integration` | 40 | 0.82 s | App, database and routing via Flask's test client |
| `e2e` | 29 | 31 s | A real headless browser against a real HTTP server |

`pytest -m unit` · `pytest -m integration` · `pytest -m e2e` · `pytest` runs all
three. No test is left unmarked, so a layer filter can never silently skip
anything — verified with `pytest -m "not unit and not integration and not e2e"`
collecting zero tests.

**Why not test everything end to end.** E2E is ~65× slower per test here and is
the only layer that can fail for reasons unrelated to the code — browser
startup, driver quirks, timing. Every one of those failures costs
investigation. So the rule is: prove it at the cheapest layer that can prove
it, and reserve the browser for what genuinely needs one — explicit waits, the
async dashboard, rendered rows, real navigation. Status codes, message
constants, SQL behaviour and the sort whitelist are all proved without a
browser and deliberately not re-proved with one.

**Fixtures compose rather than duplicate.** `seeded_db` (temp database + seed)
is the base; `client` builds the Flask test client on it; `live_server` and
`driver` build the browser stack on the same temp-database setup. One
definition of "a known starting state", shared by all three layers.

**The integration client zeroes `DASHBOARD_DELAY_MS`.** The 400 ms delay exists
to make the spinner observable in a browser; paying it on every integration
test would buy nothing. The delay is covered at the E2E layer, where it is the
whole point.

### A flake the new layers exposed, and its fix

Adding the fast layers made a latent E2E flake reproducible: the full suite
failed roughly one run in ten, at a different test each time, while
`pytest -m e2e` alone passed repeatedly.

The cause was in `LoginPage.sign_in`, which waited on
`EC.staleness_of(form)` — a **DOM-identity side effect** rather than the
outcome. When the click and the document swap interleaved badly the old element
never registered as stale and the wait timed out, even though the login had
succeeded. It now waits on the two outcomes that can actually occur: the URL
changing, or the error element appearing. Six consecutive full-suite runs
green afterwards.

Two things worth keeping from that: **wait on the result you care about, not on
an artefact of how the browser got there**, and a flake that only appears in the
full suite is usually about shared state or timing between tests, not about the
test that happens to fail.

### One expectation that was wrong, and was not "fixed" in the app

The first draft of the roster integration tests asserted `201/400/404/409` JSON
responses. Those were the Phase 1c API contract; the roster routes became
Post/Redirect/Get when the HTML form landed, so they now return 302 and report
the outcome through a flash. PRG is correct for a form — it stops a browser
refresh from re-submitting the add — so **the tests were changed, not the
route**. Same discipline as the earlier `split()[-1]` surname bug: when a new
test fails, the app is not automatically the thing that is wrong.

---

## The refresh path, and testing failure instead of success

`app/data/nba_api.py` is the live-data path. It is **out of band by design**: no
route imports it, nothing in a request touches the network, and the app serves
SQLite whether a refresh has ever succeeded or not. The measured 5 req/min tier
makes any other arrangement impossible. `python refresh.py` runs it.

**Fetch everything, validate, then write once.** A refresh fetches and validates
all pages before opening a transaction, then writes inside a single `with conn:`
block. A 429 on page two, a malformed record, or a dropped connection leaves the
cache byte-for-byte unchanged. Writing as pages arrive would leave a silently
truncated view of the data behind — which is worse than not refreshing, because
nothing about the app would look wrong.

**Failure is a value, not an exception.** `refresh_cache` returns a
`RefreshResult` with `.ok`, `.kind` and `.reason`. Callers check it. A scheduled
job should skip one refresh, not die.

**The tests are about failure, not success.** Nine of the failure modes are
covered with mocks and no network is ever touched: 429, 401/403/500/503,
non-JSON bodies, missing `data`, records missing required keys, a player whose
`team` is not an object, timeouts, connection errors, and a missing API key
(which must fail *before* any network call — asserted with
`mock_get.assert_not_called()`). Every one asserts a **fingerprint of every row
of every cache table is identical before and after**, because row counts alone
would not notice a refresh that overwrote values.

Two seams are mocked: `fetch_fn` is injected into `refresh_cache`, so transport
failures need no HTTP at all; `requests.get` is patched for the tests that
exercise `http_get` itself. stdlib `unittest.mock` was sufficient — no new
dependency.

**Graceful degradation is now proven, not asserted.** The earlier entry claimed
the app degrades to serving cached data when the source is unavailable. There is
now a test that fails a refresh and then exercises every read the app performs,
asserting all of them still return the cached rows. That closes the loop.

**Idempotency, again.** Replaying the same response produces an identical
fingerprint and identical row counts — the natural-key upsert working as
designed. Refreshing a renamed team updates the row in place rather than adding
a second one.

### One deliberate broad catch, and why

`refresh_cache` ends with `except Exception`. It is the only such catch in the
codebase and it was added because a test caught the code contradicting its own
comment: the comment promised nothing unanticipated would escape, while the
`except` clause listed specific types, so a `RuntimeError` propagated. Rather
than narrow the test, the code was made to match its documented contract — this
is a boundary for a background job, and its whole purpose is to not break its
caller. Nothing is hidden: the exception type and message are both reported on
the result. `BaseException` still propagates, so Ctrl-C and `SystemExit` behave
normally.

### Rows referencing an unknown team are skipped, not fatal

`/teams` carries 15 defunct franchises that the seed deliberately excludes, so a
fetched player or game can reference a team we do not hold. Those rows are
skipped and counted in `result.skipped` rather than being allowed to fail the
whole refresh on a foreign key. The schema needed no change to support a clean
upsert — natural keys and `ON CONFLICT(id) DO UPDATE` were already the right
shape.

---

## Random test ordering as an isolation guardrail

`pytest-randomly` shuffles the order of every run and prints the seed in the
header. Nothing about the suite asks for a particular order, so anything that
depends on one is a bug — and this makes that bug fail immediately instead of
waiting for the order to change by accident.

**It exists because this suite has already had two of those bugs, and both
hid.** The session-scoped driver leaked cookies between tests, so five auth
tests passed alone and failed together. `LoginPage.sign_in` waited on
`staleness_of`, which raced about one full run in ten and blamed a different
test each time. Both were found by luck — running the whole suite at the right
moment — and nothing in the setup would have caught either one deliberately.
Random ordering makes that class of failure surface on its own.

**A failure is reproducible.** Every run prints `Using --randomly-seed=<n>`, so
a red run replays exactly with `pytest --randomly-seed=<n>`. Verified: the same
seed collects an identical order twice, and a different seed collects a
different one. That matters for CI most of all — the seed is in the log, so a
failure that only appears on GitHub can still be reproduced locally.

CI runs bare `pytest`, so it picks up the shuffle automatically. Every push now
re-checks isolation from a different angle rather than testing the same
ordering forever.

**Result: 8 consecutive full-suite runs on 8 different seeds, all 125 green.**
Isolation now holds under randomization, and it is enforced automatically
rather than by anyone remembering to check.

This is the same principle as the seed fingerprint earlier in this file: **a
determinism claim needs a determinism test.** Asserting that tests are
independent proves nothing; shuffling them until a dependent one fails is what
proves it.

### What random ordering actually caught

The guardrail paid for itself on its first CI run. Seed 2499299644 failed
`test_clearing_the_filter_restores_the_table` with **"Node with given id does
not belong to the document"**, raised from `wait_stale` inside
`WaiverPage.apply`.

It never reproduced locally -- 4 attempts on that exact seed, plus 8 earlier
runs on other seeds, all green. CI runners are slower and more contended, which
is precisely when the window opens. So the diagnosis came from reading
Selenium's source rather than from a local repro:

    def _predicate(_):
        try:
            element.is_enabled()      # forces a staleness check
            return False
        except StaleElementReferenceException:
            return True

`staleness_of` treats **only** `StaleElementReferenceException` as success.
While Chrome is swapping documents it can instead raise a generic
`WebDriverException`, which is not caught, escapes `WebDriverWait.until`
entirely, and fails the test outright -- not even as a timeout. The wait was
never able to survive that timing.

**Same class as the login race, third occurrence, so the fix was systemic.**
All four `wait_stale` call sites -- roster add, roster remove, waiver apply,
search submit -- keyed on *element* identity. They now key on *document*
identity: `submit_and_wait` stamps a marker on `window`, clicks, and waits for
the marker to disappear, because a new document gets a fresh `window`. No
element reference is involved, so there is nothing to go stale and no node id
to become invalid. A `wait_until` helper treats any `WebDriverException` raised
mid-navigation as "ask again" rather than letting it escape the poll.

Each call site then waits on its **actual outcome** rather than on the reload:
the added row is present (or the add was refused), the removed row is gone, the
waiver table has rows or an empty state, the search settled into one of its
three states. A wait that asserts the outcome cannot pass against the
pre-submit page, which is the failure mode the earlier waits all shared.

Verified across 9 full-suite runs -- the CI seed twice plus seven fresh seeds
(1201282436, 780594957, 2316278854, 3540198208, 1041203451, 1437594772,
2272543930) -- 125 green every time.

The lesson worth carrying: **wait on the result, never on an artefact of how the
browser got there.** Element identity, staleness, and reload signals are all
proxies, and every proxy this suite has used has eventually raced. And the
guardrail did its job in the way that matters most -- it found, on a machine
that was not mine, a bug that 8 local seeds had missed.

---

## Containerizing the app and the suite

One image, two uses: serve the app, or run all 125 tests inside it with Chrome
already present. `docker compose up app` and `docker compose run --rm tests`.
Deliberately NOT in scope: Kubernetes, multiple services, or Docker as the only
way to run this. The plain `python` workflow is still the primary path and is
unchanged -- verified by running the native suite green with every new
environment variable unset.

**Why containerize a test suite at all.** The e2e layer is the part of this
project most exposed to its environment: it needs a browser, a matching driver,
and enough machine to run them. That is the classic source of "passes on my
laptop, fails in CI" -- and this suite has already been bitten by exactly that
divergence once, when a wait raced only on the CI runner. An image pins the
browser, the driver and the OS libraries together, so the environment stops
being a variable.

**Chromium and its driver come from apt, not Selenium Manager.** Selenium
Manager would download a driver on first run, which needs network access during
the test run and makes the image's behaviour depend on when it executes.
Installing `chromium` and `chromium-driver` as distro packages means the two
versions are matched by the package manager -- verified identical at
151.0.7922.137 -- so browser/driver mismatch, the classic Selenium failure,
cannot occur. `conftest` reads `CHROME_BIN` and `CHROMEDRIVER_BIN` when set and
falls back to Selenium Manager when they are not, so the same test code runs in
both places.

**Seeding happens at container start, not at build.** `seed.py` dates its three
games to the current US/Eastern date. A database baked into the image would be
stale the next day and the dashboard's "games tonight" assertions would fail for
reasons unrelated to the code. This is the same determinism concern as the seed
itself, one layer out.

**Layer order is load-bearing.** `requirements.txt` is copied and installed
before the application code, because Docker invalidates every layer after the
first changed one. Copying the tree first would re-run `pip install` on every
template edit.

**The volume exists so failure evidence survives the container.** A headless run
cannot be watched, so a failure hook writes the URL, page title and a screenshot
for any failed browser test into `/reports`, which compose mounts from the host,
alongside the JUnit XML. Without the volume all of that dies with the container
-- the same reason CI uploads artefacts. This is not hypothetical: the hook is
what produced the evidence below.

### An unresolved flake, stated plainly

The containerized e2e layer is **green when the container has the host to
itself** -- 8 consecutive full runs, 125 each, around 53s -- and **flakes at
roughly one run in four when the host is contended**, for example while images
are building or with the `app` service running alongside. Failing runs take
~80s against ~53s for green ones, and the correlation with duration is exact.

The failure hook captured two distinct signatures:

* **Session lost.** The browser sat at `/login?next=/roster/add` and
  `/login?next=/waiver`, mid-test, after the `logged_in` fixture had already
  verified an authenticated page rendered. The app behaved correctly; the
  request simply arrived without a valid session.
* **A wait expiring on a starved server.** The browser was on the dashboard
  with the right title, and a wait timed out while the dev server had not yet
  finished the fetch.

**What was ruled out.** A fixed `FLASK_SECRET_KEY` looked like a fix at 4/4
green -- until the control run, with the random key restored under the same
conditions, also went 4/4 green. The variable was host contention, not the
signing key, and the hypothesis was rejected rather than shipped as a fix.
Resources are not capped either: the container sees 16 CPUs, 15.8GB and 1GB of
`/dev/shm`.

**What was genuinely fixed along the way**, each for a stated reason rather than
to make a test pass:

* `WaiverPage.load()` waited for nothing at all, while every accessor read with
  `find_elements` and no wait. On a slower machine a read could land before the
  table rendered and quietly return an empty list -- which looks like a result,
  not a failure. It now waits for readiness.
* The `logged_in` fixture could hand back an unauthenticated browser, because
  `sign_in()` resolves on either outcome. It now verifies the authenticated nav,
  so a failed login fails at the cause instead of as a timeout three steps
  later.
* Wait budgets are now `SELENIUM_WAIT_TIMEOUT`, 10s natively and 30s in the
  image. A wait that expires while the app is still working reports a failure
  that is not there; the waits themselves are unchanged and still return the
  instant their condition holds.
* `DASHBOARD_DELAY_MS` is 1500 in the image. `driver.get()` returns at the load
  event, but `dashboard.js` starts its fetch at `DOMContentLoaded`, which is
  earlier -- so on a slow container the 400ms fetch had already resolved and the
  spinner was gone before the test could observe it. Widening the delay widens
  the window.

**The CI container job is therefore additive and non-blocking.** The native job
remains the gate. Gating on an environment that is known to flake would train
everyone to ignore red builds, which costs more than the signal is worth --
the same argument as the flake entries above. `continue-on-error` comes off when
the contention behaviour is understood, not before.
