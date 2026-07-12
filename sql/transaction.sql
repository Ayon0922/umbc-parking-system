-- =============================================================================
-- transaction.sql  —  Two-session concurrency demo (run in pgAdmin)
-- =============================================================================
-- Open TWO Query Tool tabs (Session A and Session B) and DISABLE autocommit in
-- both. Run the blocks in the numbered order, one tab at a time.
--
-- What you should observe:
--   * Session B BLOCKS on the per-spot advisory lock taken by the trigger while
--     Session A's transaction is still open.
--   * The moment Session A COMMITs, Session B unblocks, its trigger sees the now
--     committed overlapping reservation, and the INSERT fails with the
--     'Double-booking rejected' exception.
-- =============================================================================

-- ---- SESSION A -------------------------------------------------------------
BEGIN;
INSERT INTO Reservations (start_time, end_time, status, user_id, spot_id)
VALUES ('2026-09-01 10:00:00', '2026-09-01 12:00:00', 'Confirmed', 1, 1);
-- DO NOT COMMIT YET. Switch to Session B.


-- ---- SESSION B (overlapping window, same spot) -----------------------------
-- Run this in the second tab. It will HANG on pg_advisory_xact_lock(1).
BEGIN;
INSERT INTO Reservations (start_time, end_time, status, user_id, spot_id)
VALUES ('2026-09-01 11:00:00', '2026-09-01 13:00:00', 'Confirmed', 2, 1);


-- ---- SESSION A -------------------------------------------------------------
-- Back in the first tab: release the lock.
COMMIT;


-- ---- SESSION B -------------------------------------------------------------
-- The blocked INSERT now resumes and RAISES:
--   ERROR: Double-booking rejected: spot 1 is already reserved for that window.
ROLLBACK;
