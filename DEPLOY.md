# Deploying the live demo (free, no credit card)

The app self-provisions: on first boot against an **empty** PostgreSQL database
it runs `db/init/*.sql` (schema → indexes → seed) automatically. So hosting is
just two steps: stand up a free cloud Postgres, then deploy the app on Streamlit
Community Cloud pointed at it.

## Step 1 — Free cloud Postgres (Neon)

1. Go to https://neon.tech and sign in with GitHub (free tier, no card).
2. Create a project (any name). Region: pick one near you.
3. On the project dashboard, copy the **connection string**. It looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Keep `?sslmode=require` on the end.

(Supabase works too — use its "Connection string / URI" value.)

## Step 2 — Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub**:
   - Repository: `Ayon0922/umbc-parking-system`
   - Branch: `main`
   - Main file path: `app/app.py`
3. Open **Advanced settings → Secrets** and paste (see `app/.streamlit/secrets.toml.example`):
   ```toml
   DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
   APP_ADMIN_PASSWORD = "pick-a-password"
   ```
4. Click **Deploy**. First load takes ~1–2 min while it installs deps and builds
   the schema. You'll get a public URL like
   `https://umbc-parking-system.streamlit.app` — put that on your portfolio.

## Notes

- The demo is seeded with sample data and gated by `APP_ADMIN_PASSWORD`; share
  that password on the portfolio if you want visitors to click in, or set it to
  something public-friendly.
- Neon free tier sleeps when idle; the first hit after a while takes a few extra
  seconds to wake — normal.
- To wipe and re-seed the cloud DB, drop its tables (or delete/recreate the Neon
  branch) and reload the app — it re-provisions automatically.
- Local development is unchanged: `docker compose up -d --build` still works with
  no secrets (it uses the `DB_*` env defaults).
