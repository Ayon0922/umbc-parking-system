"""
db.py — configuration and connection management for the parking app.

All secrets/config come from environment variables (12-factor style), so the
same image runs locally, in Docker, or in the cloud with no code changes.
The connection is cached with @st.cache_resource and health-checked / lazily
reopened, so Streamlit reruns reuse one connection instead of leaking a new
one on every interaction (a bug in the original app).
"""
import os
import streamlit as st
import psycopg2
import pandas as pd


def _cfg() -> dict:
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "parking_db"),
        user=os.getenv("DB_USER", "umbc_admin"),
        password=os.getenv("DB_PASSWORD", "umbc_password"),
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
    )


@st.cache_resource(show_spinner="Connecting to database…")
def get_connection():
    """Return a single cached psycopg2 connection (autocommit off)."""
    conn = psycopg2.connect(**_cfg())
    conn.autocommit = False
    return conn


def _live_connection():
    """Return a healthy connection, transparently reconnecting if dropped."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        conn.rollback()          # don't leave an idle-in-transaction session open
        return conn
    except psycopg2.Error:
        # Stale/closed connection — drop the cache and rebuild.
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
    Returns a DataFrame (or text for EXPLAIN-style single-column output).
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
