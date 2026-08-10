# CLAUDE.md — Operating rules for CourtVision

Read this file at the start of every session. It is binding.

## Who this is for

Jayden Chan, 2026 Computer Engineering graduate, targeting entry-level
SDET / QA Automation / Software Engineer in Test roles. Strong in Python
and pytest. **No prior Selenium or browser-automation experience** — this
project exists to close that gap.

This repo is PUBLIC on GitHub under a real name, and every line must be
defensible in an interview. A project the author cannot explain is worse
than no project at all.

## OPERATING RULES — non-negotiable

1. **Teach before you build.** Before writing ANY code, explain what you
   are about to do, why, and what breaks if it is done the obvious-wrong
   way. The explanation is the deliverable; the code is a side effect.
2. **One phase at a time.** Stop at every phase boundary and wait for
   explicit approval. Never start the next phase unprompted.
3. **Never write more than ~100 lines before stopping.**
4. **Quiz after every phase** with exactly TWO questions. Do not proceed
   until they are answered. **Every question must be answerable from
   material already taught in this session.** Never quiz on a concept that
   has not been explained first — the quiz is a comprehension check, not a
   guessing game. If a question is worth asking but the concept was not
   covered, teach it first, in the same message, then ask.
5. **Report the state of the system at every stop.** Give both what
   CHANGED this phase and the CURRENT whole-repo structure — the tree,
   what each piece does, which files are real versus placeholders, and
   what was deliberately not built yet. A delta alone is not enough; the
   reader must be able to maintain an accurate mental model of the whole
   system without re-reading the repo.
6. **Commit after each phase** with a clear, specific message.
7. **Never hand over code that cannot be walked through line by line.**

## PROJECT CONSTRAINTS

- **Data comes from a public NBA API (BALLDONTLIE), never from scraping a
  fantasy site.** Scraping ESPN/Yahoo Fantasy is a ToS risk, is fragile,
  and reads badly to an interviewer.
- **Selenium's job is to test THIS app end to end.** It is the test layer
  for our own product. It is never a scraping tool here.
- **The free API tier is limited** (~5 req/min, basic endpoints). The real
  API covers teams / players / games / standings.
- **Injuries and player stats are SEEDED and deterministic at MVP**, not
  pulled live. Deterministic data is what makes E2E assertions stable.
- Responses are cached in SQLite rather than fetched on every page load —
  for rate limits, speed, and test determinism.
- The app must **degrade gracefully** when the data source is unavailable.

## SCOPE GUARDS — do NOT add without asking first

Allure · cross-browser matrices · BDD/behave · visual regression ·
pytest-xdist · Docker for the suite · ML recommendations · multi-user
auth · notifications.

These are later versions, not v1 requirements. A small app and suite that
is fully understood beats a sprawling one that is not.

## Reference

`fantasy-hoops-project-playbook.md` at the repo root holds the full build
plan (Phases 0–10) and the product definition. Follow it.
