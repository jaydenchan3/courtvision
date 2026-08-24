# Resume bullet

For the Projects section. Written to be defensible line by line — every claim
maps to something in this repo.

```
CourtVision — Fantasy Basketball Dashboard | Python, Flask, SQLite, Selenium, pytest, GitHub Actions

- Built a full-stack NBA dashboard (Flask + SQLite) backed by a public API,
  caching responses locally after measuring the free tier at 5 requests/minute
  so the API never sits in the page-load path
- Wrote a 29-test Selenium + pytest end-to-end suite using the Page Object
  Model, covering login, roster, waiver, and search flows, running headless on
  every push via GitHub Actions
- Eliminated flake by using explicit WebDriverWait conditions instead of sleeps
  and re-seeding both the database and browser session before every test, so
  the suite passes in any order and on repeat runs
```

## Skills line

Add to Skills: **Selenium, Page Object Model, pytest, end-to-end testing, CI/CD**

## What each claim is backed by

| Claim | Evidence |
| --- | --- |
| 5 requests/minute, measured | `spikes/probe_balldontlie.py`; `x-ratelimit-limit: 5` recorded in DECISIONS.md |
| 29 tests, five areas | `pytest --collect-only`; markers `auth`/`dashboard`/`roster`/`waiver`/`search` |
| Page Object Model | `tests/pages/` — locators and actions only, assertions live in tests |
| Explicit waits, no sleeps | `tests/pages/base_page.py`; no `time.sleep` and no implicit wait in the suite |
| Passes in any order, repeatably | Verified green twice consecutively and with test files run in reverse |
| Headless in CI | `.github/workflows/ci.yml`, no secrets required |

## The interview answer to practise

> "I used a public API rather than scraping a fantasy site, because that's the
> maintainable and legally clean choice — and I used Selenium where it actually
> belongs, as the end-to-end test layer for my own app. The hardest part wasn't
> writing the tests, it was making them trustworthy: I hit a bug where five auth
> tests passed individually and failed as a suite, because my driver was
> session-scoped and its cookies outlived each test. Re-seeding the database
> wasn't enough isolation when the browser was shared too."
