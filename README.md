# UMBC Parking Management System

A parking-operations database with a web admin console. PostgreSQL schema
(triggers, stored routines, views), a Streamlit UI, and a one-command Docker
stack. CMSC 461 — production-hardened build.

## Stack

| Service | What | URL |
|---|---|---|
| `db` | PostgreSQL 15, schema + seed auto-loaded on first boot | `localhost:5432` |
| `app` | Streamlit admin console | http://localhost:8501 |
| `pgadmin` | Optional web DB client | http://localhost:5050 |

## Quick start (Docker — recommended)

```bash
cp .env.example .env        # then edit passwords if you like
docker compose up -d --build
```

Open **http://localhost:8501** and sign in with the `APP_ADMIN_PASSWORD` from
your `.env` (default `admin`). On first boot the database initialises itself by
running, in order, `db/init/01_schema.sql`, `02_indexes.sql`, `03_seed.sql` — no
manual load step.

To reset the database completely:

```bash
docker compose down -v && docker compose up -d --build   # -v wipes the volume
```

## Connecting with pgAdmin

Open http://localhost:5050, log in with `PGADMIN_EMAIL` / `PGADMIN_PASSWORD`
from `.env`, then **Add New Server**:

- Host: `db`  (the compose service name; use `localhost` if connecting from your host machine)
- Port: `5432`
- Database: `parking_db`
- Username: `umbc_admin`
- Password: `umbc_password`

(These are the **database** credentials from `.env` — distinct from the pgAdmin
login above.)

## Run the app without Docker

```bash
# Postgres must be running and loaded with db/init/*.sql
cd app
pip install -r requirements.txt
export DB_HOST=localhost DB_USER=umbc_admin DB_PASSWORD=umbc_password DB_NAME=parking_db
streamlit run app.py
```

All connection settings are read from environment variables (`DB_HOST`,
`DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `APP_ADMIN_PASSWORD`) with
sensible localhost defaults — see `app/db.py`.

## Repository layout

```
parking-system/
├── docker-compose.yml        # db + app + pgadmin
├── .env.example              # copy to .env
├── db/init/                  # auto-loaded on first DB boot
│   ├── 01_schema.sql         # tables, FKs, triggers, functions, procedure, views
│   ├── 02_indexes.sql        # performance indexes
│   └── 03_seed.sql           # sample data (>=10 rows/table)
├── sql/                      # manual pgAdmin scripts
│   ├── dropDDL.sql           # full reset
│   ├── queryAll.sql          # 10 course-level queries
│   └── transaction.sql       # two-session concurrency demo
└── app/                      # Streamlit admin console
    ├── app.py  db.py  requirements.txt  Dockerfile  .streamlit/config.toml
```

## Core database features

- **Sensor occupancy trigger** (`trg_sensor_occupancy`) flips `Spots.is_occupied`
  when a `SensorEvents` row is inserted.
- **Double-booking prevention** (`trg_prevent_double_booking`) rejects
  overlapping confirmed reservations for the same spot. It takes a per-spot
  `pg_advisory_xact_lock` so the check is safe under real concurrency, and
  excludes the row being updated so legitimate updates don't self-conflict.
- **`issue_permit(v_id, t_id, start_date)`** enforces one active permit per
  vehicle and derives expiry from the permit type's duration.
- **`auto_generate_tickets()`** fines occupied spots whose current reservation
  holder has no valid permit; idempotent (won't duplicate open tickets).
- **Views**: `CurrentLotAvailability`, `ActivePermitUserList`.

## Concurrency demo

Programmatic version: the app's **Concurrency Demo** tab. True blocking version:
run `sql/transaction.sql` in two pgAdmin Query Tool tabs with autocommit off —
Session B blocks on the advisory lock until Session A commits, then fails with a
double-booking exception.

## Notes

- `.env` holds secrets and is git-ignored; commit only `.env.example`.
- The admin login and the SELECT-only "Custom SQL" panel are basic safeguards
  for a coursework/demo deployment, not a substitute for real authn/z.
