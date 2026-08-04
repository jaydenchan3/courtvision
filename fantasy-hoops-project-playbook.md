# Fantasy Basketball App + Selenium/pytest Suite — Project Playbook

A complete brief for a fresh Claude chat (and Claude Code behind it). Paste Part 1 into a
new conversation and it will have your full context. The rest is the spec that chat turns
into Claude Code prompts, one phase at a time.

---

## A decision made up front, and why (read this first)

The original idea used Selenium to log into ESPN/Yahoo Fantasy and scrape your roster. That
is dropped on purpose, for three reasons: it likely violates those sites' Terms of Service,
an interviewer may read "I automated a site that forbids automation" as a red flag rather
than a strength, and scraping a logged-in commercial site is fragile busywork that eats the
time meant for the test suite.

The fix costs you nothing. Every Selenium skill worth showing (login flows, explicit waits,
dynamic content, tables, forms, page objects) is practiced against YOUR OWN app. That is
also how Selenium is actually used on the job: to test your product, not to scrape someone
else's. So:

- Data comes from a public NBA API, not from scraping a fantasy site.
- The "personal roster" feature works by letting the user enter/paste their own players.
- Selenium's role is the end-to-end TEST layer for your own app. This is the strongest and
  most honest version of the project.

## DATA SOURCE — verified live, but confirm the free tier yourself in Phase 0

Checked live in this session (late July 2026). Both options below were active. APIs change
pricing, add auth, and shrink free tiers with little notice, so treat this as a starting
point and confirm the specifics with real calls before designing around any endpoint.

PRIMARY: BALLDONTLIE (balldontlie.io)
- Active and expanded. Covers NBA plus 20+ leagues. Advertises a free tier. NBA endpoints
  include /nba/v1/games, /nba/v1/box_scores, /nba/v1/standings, returning live data through
  the current day.
- IMPORTANT: the base URL and structure CHANGED since older tutorials. It is now
  api.balldontlie.io/nba/v1/... and appears to require an API key. Follow the CURRENT docs
  at balldontlie.io, not any pre-2024 blog post or code sample.
- UNCONFIRMED and you must check in Phase 0: the exact free-tier rate limits and which
  endpoints the free tier includes. "Free tier available" was stated; the numbers were not.
  Those limits determine whether this works for your project, which is why you cache
  responses in SQLite rather than calling the API on every page load.

BACKUP: nba_api / nba_data (Python packages wrapping stats.nba.com)
- Exists and installable from PyPI. Use only if BALLDONTLIE's free tier turns out too
  limited.
- KNOWN RISK: stats.nba.com makes no guarantees about uptime or breaking changes and has
  essentially no official documentation. It also rate-limits aggressively and sometimes
  blocks non-browser traffic. Workable as a fallback, riskier as a primary.

DECISION RULE: try BALLDONTLIE first. If its free tier blocks what you need, fall back to
nba_api. If BOTH fail, the app still works with manually entered / seeded data for the demo
and tests, so a dead API never blocks the project. Note that fallback in DECISIONS.md; "the
app degrades gracefully when the data source is unavailable" is a good engineering point to
be able to make.

Do not take any API on faith. Phase 0 is a spike: make real calls with your own key, read
the real JSON, confirm the free tier covers your use, THEN design around it.

---

## PART 1 — Context block (paste into a new Claude chat)

```
I'm building a full-stack fantasy basketball web app AND a Selenium + pytest end-to-end
test suite for it, in Python. Help me plan, then help me write prompts I'll paste into
Claude Code to build it phase by phase. Context:

WHO I AM
2026 Computer Engineering graduate. Software engineering contractor at Handshake AI doing
test-infrastructure work (fail-to-pass suites, Dockerfiles, CI). Strong in Python and
JavaScript, know pytest well, have never used Selenium. Zero browser automation experience.
This project closes that gap.

WHY THIS PROJECT
Two goals at once. (1) Learn Selenium + pytest deeply, because a referral told me their team
uses that stack and building in it gives me an edge. (2) Have a real shipped full-stack app
on my GitHub. Target roles: entry-level SDET / QA Automation / Software Engineer in Test.

CRITICAL CONSTRAINT
This goes on my public GitHub with my name on it and I have to defend every line in an
interview. A project I can't explain is worse than none. When we use Claude Code, the
prompts must make it TEACH and QUIZ me, not just deliver code. Stop at each phase, explain
before writing, quiz me after. Never hand me a repo I can't walk through.

A DESIGN DECISION ALREADY MADE
Data comes from a PUBLIC NBA API, not from scraping any fantasy site (ToS risk + fragility +
it reads badly to interviewers). Users enter their own roster manually. Selenium's job is to
TEST my own app end to end, which is how Selenium is actually used professionally.
API plan (verified live late July 2026, but I must re-confirm the free tier in a Phase 0
spike): PRIMARY is BALLDONTLIE (api.balldontlie.io, current docs, likely needs a free key).
BACKUP is the nba_api Python package (wraps stats.nba.com, no uptime guarantees). If both
fail, the app runs on seeded/manual data so a dead API never blocks it. Help me spike the
API for real before designing around it.

WHAT I WANT FROM YOU
1. Confirm the API and the MVP scope with me.
2. Help me write the need/goal statement and a short product spec.
3. Write Claude Code prompts one phase at a time, teach-and-quiz style.
4. At the end, help me write the README and the resume bullet.
Ask me anything you need, then let's lock the plan.
```

---

## PART 2 — Product definition (write this before any code)

A portfolio project reads as senior when it starts from a problem, not a tool.

**Need statement.**
Fantasy basketball managers check several scattered sources every day (matchup, injuries,
who plays tonight, waiver options) to make lineup decisions. The information exists but is
spread across pages, and pulling it together takes 10-20 minutes daily.

**Goal statement.**
Build a personal dashboard that pulls key NBA information into one place and turns it into
clear daily lineup guidance, so a manager can make decisions in under two minutes instead of
hunting across sites.

**Target user.** You, first. Solving your own problem is a strength, not a weakness. Multi-
user comes later if at all.

**What the product answers**, without the user hunting:
- Which of my players play tonight?
- Who's injured or questionable?
- Who's trending up or down?
- Which available players are worth adding?

**What it deliberately is NOT (scope guard).** Not a scraper of anyone's fantasy account. Not
a live-updating production service. Not multi-user at MVP. Not an ML recommender at MVP. Each
of those is a possible later version, not a v1 requirement.

**Give it a product name** so you can say "I built CourtVision" rather than "I built a
Selenium project." Pick one you like: CourtVision, FastBreak, HoopIQ, WaiverWire, BenchBoss.

---

## PART 3 — Build plan (the spec the new chat turns into Claude Code prompts)

Rules for every Claude Code prompt (same as your other playbooks):
- One phase at a time. STOP at each boundary and wait.
- Explain what and WHY before writing, including what breaks if done the obvious-wrong way.
- Quiz me with two questions after each phase; don't proceed until I answer.
- Never more than ~100 lines without stopping.
- Commit after each phase with a clear message.

Repo name: courtvision (or whatever you named it). Target structure:
```
courtvision/
├── README.md
├── DECISIONS.md
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── server.py          # Flask backend
│   ├── data/
│   │   ├── nba_api.py      # public API client (with caching)
│   │   └── models.py       # SQLite schema
│   ├── static/            # CSS, minimal JS
│   └── templates/         # HTML pages
├── seed.py                # deterministic seed data for tests
├── tests/
│   ├── conftest.py        # driver fixture, waits, test data
│   ├── pages/             # Page Object Model
│   │   ├── base_page.py   # shared explicit-wait helpers
│   │   ├── dashboard_page.py
│   │   ├── roster_page.py
│   │   └── waiver_page.py
│   └── test_*.py
├── .github/workflows/e2e.yml
└── pytest.ini
```

Build in three arcs. Learn the app first, then make it testable, then prove QA skill.

### ARC A — The app (build something real to test)

PHASE 0 — API spike and data model.
Spike the API BEFORE designing anything around it. Try BALLDONTLIE first (api.balldontlie.io,
current docs, likely needs a free API key). Make real calls to the games/standings endpoints,
read the actual JSON, and record the free-tier rate limits and which endpoints are included.
If the free tier is too limited, fall back to nba_api. If both fail, the app runs on
seeded/manual data so a dead API never blocks you. See the DATA SOURCE section at the top of
this playbook for the full detail and the decision rule.
Then explain why you cache API responses in SQLite instead of calling the API on every page
load (rate limits, speed, and test determinism), and design the SQLite schema: players,
teams, games, injuries, and a user_roster table the user fills manually. Seed a known
deterministic state for tests. Record the API choice and the graceful-degradation fallback in
DECISIONS.md.

PHASE 1 — Flask backend + routes.
Minimal Flask app. Routes for: dashboard, roster management (add/remove players), waiver
view, player search, login/logout. Explain why deterministic seed data matters for E2E
testing before wiring the DB in. Keep it small; the app serves the tests, don't gold-plate.

PHASE 2 — The pages (minimal but real UI).
HTML + a little CSS + minimal JS. Each screen is chosen to give a distinct thing to test:
- Login / logout                      -> auth, session, explicit wait on redirect
- Dashboard: tonight's games, injuries -> async data load, empty states, a loading spinner
- Roster: add/remove players, a table  -> forms, tables, dynamic content
- Waiver: sortable/filterable list     -> sorting, filtering, dynamic rerender
- Player search                        -> search with results and a no-results empty state
Add a deliberate 300-500ms delay + spinner on the dashboard load. This is the explicit-wait
teaching case for the test suite.

### ARC B — Selenium foundations (the new skill)

PHASE 3 — Selenium + pytest scaffold.
webdriver-manager vs manual drivers (and why version mismatch is a classic Selenium
failure). conftest.py driver fixture: scope, setup, teardown, and why teardown matters
(leaked browser processes). Headless in CI, headed locally. pytest.ini and markers.

PHASE 4 — Explicit waits (THE core phase; spend real time here).
This is the reason it's Selenium and the thing interviews probe. Explain before coding:
- Why Selenium does NOT auto-wait and what that means for you
- implicit vs explicit wait vs time.sleep(), why time.sleep is nearly always wrong, and why
  mixing implicit and explicit waits is a known trap
- WebDriverWait + expected_conditions: element_to_be_clickable,
  visibility_of_element_located, presence_of_element_located, and when each is right
- why waits live in base_page.py, not copy-pasted into every test
Wait correctly on the dashboard spinner from Phase 2.

PHASE 5 — Locators + Page Object Model.
Locator strategies (By.ID, By.NAME, By.CSS_SELECTOR, By.XPATH) and a priority order (stable
ids/names first, brittle CSS/XPath last). Why styling-class locators break silently on a
refactor. Why POM is expected in professional Selenium work. Build page objects: locators +
actions only, no assertions, actions return void or another page object, no test data
inside them, all waits through the base helper.

### ARC C — The test suite + QA skill (the payoff)

PHASE 6 — The test plan (write it before the tests).
Put it in DECISIONS.md as a table: test name, what it verifies, which QA technique. You're
learning QA vocabulary alongside this and want the mapping explicit. Minimum coverage:
- AUTH: valid login; wrong password (error, no nav); logout clears session; protected route
  while logged out redirects
- DASHBOARD: loads after spinner (explicit wait); tonight's games render; injuries widget
  renders; empty state when no games
- ROSTER: add a player, appears in table; remove a player, gone; invalid add rejected
- WAIVER: sort changes order; filter narrows; clearing restores
- SEARCH: found player shows; unknown shows empty state, not a blank page
- BOUNDARY/VALIDATION: roster size cap enforced; duplicate player rejected
Rules, each explained: every test independent and any-order; every test makes its own data
with a unique id (explain why under parallel runs); assert on user-visible outcomes; no
if/else inside tests.

PHASE 7 — Fixtures, data, parametrize.
conftest fixtures for setup/teardown; parametrize the validation/boundary cases; a unique-
data factory; cleanup strategy (per-test vs reset vs unique-and-leave), justified.

PHASE 8 — CI (GitHub Actions).
Headless on every push and PR: install deps, cache browser/driver, start Flask, wait for
genuine readiness, run pytest, upload HTML report + screenshots-on-failure as artifacts.
Explain: readiness poll vs sleep, why screenshots matter for a headless run you can't watch,
keeping it under ~5 minutes.

PHASE 9 — The flake lab (interview gold; Selenium flake is mostly wait mistakes).
For each: show the failure, explain the mechanism, fix it.
1. time.sleep(0.1) racing the 400ms dashboard spinner -> WebDriverWait
2. missing wait on a dynamically added roster row     -> visibility wait
3. two parallel tests sharing a fixed player          -> unique data
4. implicit + explicit wait mixed, weird long hangs   -> remove implicit
Then a DECISIONS.md note: flaky test vs real bug, and why retrying a genuine race is worse
than a red build.

PHASE 10 — Docs.
README leads with BOTH stories: it's a real app AND it has a professional test suite. How to
run the app, how to run the tests, how to run one test, how to read the report, structure, CI
badge. DECISIONS.md: one entry per real decision (why an API not scraping, caching strategy,
explicit-wait approach, locator strategy, POM boundary, isolation/data, CI readiness, test-
plan technique mapping). Then quiz me on eight things and tell me which answers were weak.

### Scope discipline
Do NOT add without asking: Allure (unless the referral uses it), cross-browser matrices, BDD/
behave, visual regression, parallel-xdist, Docker for the suite, ML recommendations,
multi-user auth, notifications. Those are LATER VERSIONS. A small app + suite you fully
understand beats a sprawling one you don't.

### If you run short on time
Cut in this order: waiver sorting/filtering tests, then search tests, then two flake
scenarios, then trim the UI to dashboard + roster only. NEVER cut: Phase 4 (waits), Phase 9
flake basics, or DECISIONS.md. Those are what make it defensible instead of a tutorial.

---

## PART 4 — Versions beyond MVP (build only if a real need appears)

The MVP is Arcs A-C: app + tests + CI, shipped. Do not build these until the MVP is on
GitHub. Each should be driven by an actual gap you feel using it, not added for show.

- v2: recommendations ("bench X, only 2 games this week; start Y") — turns dashboard into
  assistant. New logic = new tests.
- v3: a daily morning summary (email/Discord) — a scheduler + a notification. New flows to
  test.
- v4: multiple users / real accounts — only if you want to practice auth and multi-tenancy.
Each version adds features, which adds tests, which is the point. Let user need drive it.

---

## PART 5 — After MVP ships

Push to github.com/jaydenchan3. Description: "Full-stack fantasy basketball dashboard (Flask,
SQLite, public NBA API) with a Selenium + pytest end-to-end test suite running in CI." Pin it.

Resume bullet (Projects section, plain-English to match your others):
```
CourtVision: Fantasy Basketball Dashboard | Python, Flask, Selenium, pytest, GitHub Actions
- Built a full-stack dashboard that pulls NBA data from a public API into daily lineup
  guidance, backed by SQLite and served with Flask
- Wrote a Selenium and pytest end-to-end suite (N tests) covering login, roster, and search
  flows, running headless in CI with screenshots on failure
- Cut test flakiness by using explicit waits and giving each test its own isolated data
```
Fill in N. Add to Skills: Selenium, Page Object Model, Flask, end-to-end testing.

The interview answer this sets up (practice it): "I used a public API for data because that's
the reliable, maintainable choice, and I used Selenium where it actually belongs, as the
end-to-end test layer for my own app. That's how it's used in practice."

---

## PART 6 — Don't let building crowd out applying

This is a bigger project than a bare test suite, so it's easy to disappear into it for
weeks. Don't. Keep applying with the resumes you already have while you build. Ship the MVP,
put it up, add the bullet, then get back to applications and referral outreach. One shipped
app + suite is plenty; you do not need to build v2-v4 before you start interviewing.
