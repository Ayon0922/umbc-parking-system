-- =============================================================================
-- 02_indexes.sql  —  Performance indexes
-- =============================================================================
-- License-plate lookups (enforcement / search).
CREATE INDEX idx_vehicle_plate ON Vehicles(license_plate);

-- Double-booking check filters by spot_id first, then the time window, so a
-- composite (spot_id, start_time, end_time) index serves it far better than
-- the original (start_time, end_time)-only index.
CREATE INDEX idx_res_spot_time ON Reservations(spot_id, start_time, end_time);

-- Partial index: the overlap trigger only ever scans Confirmed rows.
CREATE INDEX idx_res_confirmed ON Reservations(spot_id) WHERE status = 'Confirmed';

-- Spot lookups by lot.
CREATE INDEX idx_spot_lot ON Spots(lot_id);

-- Permit expiry checks (active-permit filters throughout the app).
CREATE INDEX idx_permit_expiry  ON Permits(expiry_date);
CREATE INDEX idx_permit_vehicle ON Permits(vehicle_id);

-- Ticket joins in enforcement / payments reporting.
CREATE INDEX idx_ticket_vehicle ON Tickets(vehicle_id);
CREATE INDEX idx_ticket_status  ON Tickets(status);
CREATE INDEX idx_payment_ticket ON Payments(ticket_id);

-- User email lookups.
CREATE INDEX idx_user_email ON Users(email);
