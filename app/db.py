"""
db.py — configuration, connection management, and self-provisioning.

Config resolution order (first hit wins), so the same code runs locally, in
Docker, and on Streamlit Community Cloud with no edits:
  1. DATABASE_URL           (st.secrets or env)  — e.g. a Neon/Supabase URL
  2. DB_HOST/DB_PORT/...     (st.secrets or env)  — discrete vars (Docker)
  3. localhost defaults      (local dev)

On first connection the app calls ensure_schema(): if the `roles` table is
missing it runs db/init/*.sql (schema -> indexes -> seed) inside an advisory
lock, so pointing the app at an EMPTY cloud database is all that's needed —
no manual load step.
"""
import os
import glob
import streamlit as st
import psycopg2
import pandas as pd

# Repo root = parent of app/ ; the init SQL lives in db/init/*.sql
_INIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "init")


def _secret(name, default=None):
    """Look in st.secrets first (Streamlit Cloud), then env, then default."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def _conn_kwargs():
    url = _secret("DATABASE_URL")
    if url:
        # psycopg2 accepts a libpq URL/DSN directly.
        return {"dsn": url, "connect_timeout": int(_secret("DB_CONNECT_TIMEOUT", "8"))}
    return dict(
        host=_secret("DB_HOST", "localhost"),
        port=int(_secret("DB_PORT", "5432")),
        dbname=_secret("DB_NAME", "parking_db"),
        user=_secret("DB_USER", "umbc_admin"),
        password=_secret("DB_PASSWORD", "umbc_password"),
        connect_timeout=int(_secret("DB_CONNECT_TIMEOUT", "8")),
    )


def admin_password():
    return _secret("APP_ADMIN_PASSWORD", "admin")


@st.cache_resource(show_spinner="Connecting to database…")
def get_connection():
    """Return a single cached psycopg2 connection (autocommit off)."""
    kw = _conn_kwargs()
    conn = psycopg2.connect(**kw) if "dsn" not in kw else psycopg2.connect(kw["dsn"], connect_timeout=kw["connect_timeout"])
    conn.autocommit = False
    return conn


@st.cache_resource(show_spinner="Preparing database (first run only)…")
def ensure_schema():
    """
    Idempotently create schema + seed on an empty database. Safe to call on
    every startup; it no-ops once the tables exist. Uses a transaction advisory
    lock so two simultaneous cold starts don't both try to build the schema.
    Returns a status string.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(918273645);")   # arbitrary app-wide key
            cur.execute("SELECT to_regclass('public.roles');")
            if cur.fetchone()[0] is not None:
                conn.rollback()
                return "already-initialised"
            for path in sorted(glob.glob(os.path.join(_INIT_DIR, "*.sql"))):
                with open(path, "r", encoding="utf-8") as fh:
                    cur.execute(fh.read())      # psycopg2 runs multi-statement files
            conn.commit()
            return "initialised"
    except Exception:
        conn.rollback()
        raise


def _live_connection():
    """Return a healthy connection, transparently reconnecting if dropped."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        conn.rollback()          # don't leave an idle-in-transaction session open
        return conn
    except psycopg2.Error:
        get_connection.clear()
        return get_connection()


def run_query(query, params=None, commit=False):
    """
    Execute a query.
      * SELECT / RETURNING  -> pandas.DataFrame
      * DML / CALL          -> None
    Rolls back and re-raises on error so the app never sits in an aborted txn.
    """
    conn = _live_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                if commit:
                    conn.commit()
                return pd.DataFrame(rows, columns=cols)
            if commit:
                conn.commit()
            return None
    except Exception:
        conn.rollback()
        raise


def run_readonly(query, params=None):
    """
    Run an untrusted SELECT inside a READ ONLY transaction and always roll back,
    so the custom-SQL panel can never mutate data even if the guard is bypassed.
    """
    conn = _live_connection()
    try:
        conn.rollback()   # ensure a fresh txn so SET TRANSACTION is the first stmt
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY;")
            cur.execute(query, params)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                return pd.DataFrame(rows, columns=cols)
            return None
    finally:
        conn.rollback()
