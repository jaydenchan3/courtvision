# CLAUDE.md — Operating rules for CourtVision

Read this file at the start of every session. It is binding.

## Who this is for

Jayden Chan, 2026 Computer Engineering graduate, targeting entry-level
SDET / QA Automation / Software Engineer in Test roles. Strong in Python,
pytest, Flask and SQL. Learning Selenium and browser automation — that is
the gap this project exists to close.

This repo is PUBLIC on GitHub under a real name, and every line must be
defensible in an interview.

## OPERATING RULES

1. **No quizzes.** No general Python, Flask, or SQL explanation — those are
   already known.
2. **Explain only QA/SDET-specific things**: Selenium mechanics, waits,
   locator strategy, Page Object Model, test isolation, fixtures, flake,
   CI. A few sentences at most, and only when a real testing decision is
   being made.
3. **Verify before committing.** Run it and show the output. A claim that
   something works is not the same as evidence.
4. **One commit per chunk**, with a real message explaining the decisions.
5. **DECISIONS.md gets an entry** only for QA-relevant decisions, or ones a
   reviewer would question.
6. **Print a 3–5 line status at each chunk boundary**, then continue without
   stopping to ask. Stop only if genuinely ambiguous or a scope guard is at
   risk.

## TEST SUITE RULES — non-negotiable

- **No `time.sleep()` anywhere in the suite.** Every wait is a
  `WebDriverWait` on an explicit `expected_condition`. Sleeps race the
  application and are the single largest source of Selenium flake.
- **Never mix implicit and explicit waits.** No implicit wait is set at all.
- **Locators live in page objects**, as class-level `By` tuples, targeting
  `id` or `data-testid` hooks. Never CSS-class locators, never absolute
  XPath, never inline locators in a test.
- **Page objects hold locators and actions, not assertions.** Tests call
  page methods and assert on what they return.
- **Every test starts from the identical seeded state** and must pass in any
  order, run repeatedly.
- **Tests import message constants from `app.server`**, never a pasted copy
  of the text.
- **Tests never touch `courtvision.db`** — the suite runs against a
  throwaway database via the DB path override.

## PROJECT CONSTRAINTS

- **Data comes from a public NBA API (BALLDONTLIE), never from scraping a
  fantasy site.** Selenium's job is to test THIS app end to end.
- **Free tier measured at 5 req/min**; `/standings` and `/players/active`
  are 401 (paid). Responses are cached in SQLite, never fetched per request.
- **Injuries and player stats are SEEDED and deterministic at MVP.**
  Determinism is what makes E2E assertions stable.
- The app must **degrade gracefully** when the data source is unavailable.

## SCOPE GUARDS — do NOT add without asking first

Allure · cross-browser matrices · BDD/behave · visual regression ·
pytest-xdist / parallel runs · Docker for the suite · ML recommendations ·
multi-user auth · notifications.

Target is **one headless Chrome**.

## Reference

`fantasy-hoops-project-playbook.md` holds the full build plan.
`DECISIONS.md` holds the argued decisions and the measured API findings.
