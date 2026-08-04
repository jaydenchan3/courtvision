# CourtVision

Full-stack fantasy basketball dashboard (Flask, SQLite, public NBA API) with a
Selenium + pytest end-to-end test suite running in CI.

> **Status: in development.** Phase 0a (scaffold) complete. This README is a
> stub and is written properly in Phase 10.

## The problem

Fantasy basketball managers check several scattered sources every day — matchup,
injuries, who plays tonight, waiver options — and pulling it together takes
10–20 minutes daily.

## The goal

One dashboard that answers the daily questions in under two minutes:

- Which of my players play tonight?
- Who is injured or questionable?
- Who is trending up or down?
- Which available players are worth adding?

## Two stories, on purpose

1. **It is a real app** — Flask backend, SQLite persistence, live data from the
   public BALLDONTLIE NBA API.
2. **It has a professional test suite** — Selenium + pytest end-to-end coverage
   using the Page Object Model and explicit waits, running headless in CI with
   screenshots on failure.

Selenium is used here the way it is used on the job: as the end-to-end test
layer for our own product, not to scrape anyone else's site.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # then paste your free BALLDONTLIE key
```

## Running the app

_To be written in Phase 1._

## Running the tests

_To be written in Phase 3._

## Repo structure

```
app/          Flask application package
  data/       API client + SQLite models (data access, kept out of routes)
  static/     CSS and minimal JS
  templates/  HTML pages
seed.py       Deterministic seed data for tests
tests/        pytest + Selenium suite
  pages/      Page Object Model
spikes/       Throwaway exploration scripts (e.g. the Phase 0b API probe)
.github/workflows/   CI
```

## Design decisions

See [DECISIONS.md](DECISIONS.md).
