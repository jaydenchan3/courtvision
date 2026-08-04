"""Deterministic seed data for CourtVision.

Placeholder — implemented in Phase 0b, after the SQLite schema is designed.

Purpose: put the database into a known, fixed state so end-to-end tests can
assert on exact values ("the dashboard shows 3 games tonight"). Tests that
depend on live API data fail for reasons unrelated to the code, which is how
an E2E suite loses the team's trust.
"""
