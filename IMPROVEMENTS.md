# What changed and why

This build consolidates the two divergent copies of the project (`zipping/` and
`part1/sql/`) into one clean, working, deployable project, and fixes the bugs
found in each.

## Bugs fixed

### Application (`zipping/app.py` — the version that was actually submitted)
1. **Tab index mismatch.** 8 tabs were declared but only `tabs[0..5]` were
   filled, so the Concurrency Demo rendered under the *Payments* tab and the
   *SQL Reports* / *Concurrency Demo* tabs were blank. The new app binds every
   tab to a named handle, so this class of bug can't recur.
2. **`st.experimental_rerun()` (×3) is removed in Streamlit ≥ 1.27.** With an
   unpinned `streamlit`, a fresh install crashed on any button press. Replaced
   with `st.rerun()` and the dependency is now pinned.
3. **Connection leak.** A new DB connection was opened on every script rerun.
   Now a single connection is cached with `@st.cache_resource` and
   health-checked / reopened on demand (`app/db.py`).

### Database schema
4. **Double-booking trigger self-conflicted on UPDATE.** The overlap check
   compared the new row against *all* confirmed rows including itself, so any
   `UPDATE` of a confirmed reservation threw a false conflict. Fixed with
   `res_id <> NEW.res_id`.
5. **Double-booking race condition.** Two concurrent transactions could both
   pass the `EXISTS` check before either committed. Added
   `pg_advisory_xact_lock(NEW.spot_id)` to serialise per spot.
6. **`auto_generate_tickets()` produced duplicates.** Re-running it re-issued
   tickets for the same vehicle/spot. Added a `NOT EXISTS` guard so it's
   idempotent.
7. **`issue_permit()` hard-coded a 180-day expiry** regardless of permit type.
   It now derives expiry from `PermitTypes.duration_days` and returns the new
   `permit_id`.

### Data & queries
8. **Payments seed was internally inconsistent** — 10 payments mapped to only 3
   tickets with amounts exceeding the fines. Rebuilt so every payment maps to a
   `Paid` ticket and installments sum *exactly* to each fine (verified
   programmatically).
9. **Query #10 ("revenue per permit type") was wrong** — it summed fine
   *payments* through vehicles, not permit revenue. Corrected to
   `COUNT(permits) × type cost`, with the fine-collection query kept as a
   clearly-labelled companion (`10b`).
10. **Query #9 self-join** now emits each conflicting pair once (`r1.res_id <
    r2.res_id`) and filters to `Confirmed` rows.

### Docs / infra
11. **README credential mismatches** (password `admin` vs `admin_password`),
    `https://localhost:5050` (should be `http`), and missing DB credentials —
    all corrected and expanded.

## Production hardening added

- **Referential integrity.** Foreign keys are `NOT NULL` where a child is
  meaningless without its parent, with explicit `ON DELETE CASCADE/RESTRICT`.
  `status`, `event_type`, cost/amount fields carry `CHECK` constraints. Added
  `created_at` audit columns.
- **Better indexes.** Composite `(spot_id, start_time, end_time)` and a partial
  index on confirmed reservations to serve the overlap check; extra indexes on
  ticket/payment/permit join keys.
- **12-factor config.** All secrets come from environment variables (`.env`);
  nothing is hard-coded. `.env` is git-ignored, `.env.example` is committed.
- **Containerised app.** `app/Dockerfile` (non-root, healthcheck) plus a
  `docker-compose.yml` that runs db + app + pgadmin, waits for a healthy DB, and
  **auto-loads** the schema/seed via `/docker-entrypoint-initdb.d`.
- **Basic authn + query safety.** A login gate (`APP_ADMIN_PASSWORD`), the
  license-plate search is parameterised (was string-interpolated → SQL
  injection), and the custom-SQL panel runs inside a `READ ONLY` transaction
  that is always rolled back, rejecting non-`SELECT` and multi-statement input.

## Verification performed

- `python -m py_compile` on `app.py` and `db.py` — pass.
- SQL files parsed with `sqlglot` (Postgres dialect) — pass.
- Seed integrity checked programmatically: payment installments equal fines for
  all Paid tickets; no two Confirmed reservations overlap on the same spot (so
  the seed load won't trip the double-booking trigger).

> Not run here: a live end-to-end `docker compose up` (no Docker in the build
> environment). The schema is standard PostgreSQL 15; run the Quick Start in the
> README to exercise it.
