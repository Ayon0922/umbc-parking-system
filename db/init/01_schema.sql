-- =============================================================================
-- 01_schema.sql  —  UMBC Parking Management System (Physical Schema)
-- CMSC 461 · Production-hardened build
-- =============================================================================
-- Run order (auto-loaded by Postgres from /docker-entrypoint-initdb.d):
--   01_schema.sql -> 02_indexes.sql -> 03_seed.sql
--
-- Hardening notes vs. the original createDDL.sql:
--   * FKs are NOT NULL where a child row is meaningless without a parent, and
--     carry explicit ON DELETE actions (RESTRICT / CASCADE) for referential
--     integrity instead of silently allowing orphans.
--   * status columns are constrained with CHECK IN (...) so bad states can't
--     be inserted.
--   * created_at audit columns added to the operational tables.
--   * The double-booking trigger now (a) excludes the row being updated so a
--     legitimate UPDATE no longer self-conflicts, and (b) takes a per-spot
--     transaction advisory lock to close the check-then-insert race under real
--     concurrency.
--   * auto_generate_tickets() is idempotent: it will not issue a second open
--     ticket for a vehicle/spot that already has one.
-- =============================================================================

-- ----------------------------------------------------------------------------
-- Lookup / reference tables
-- ----------------------------------------------------------------------------
CREATE TABLE Roles (
    role_id   SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Users (
    user_id    SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100) NOT NULL UNIQUE,
    role_id    INT NOT NULL REFERENCES Roles(role_id) ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE Vehicles (
    vehicle_id    SERIAL PRIMARY KEY,
    license_plate VARCHAR(20) NOT NULL UNIQUE,   -- Business Rule 1
    make          VARCHAR(50),
    model         VARCHAR(50),
    color         VARCHAR(20),
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

-- M:N — a vehicle may be shared by multiple users and vice-versa.
CREATE TABLE User_Vehicles (
    user_id    INT NOT NULL REFERENCES Users(user_id)      ON DELETE CASCADE,
    vehicle_id INT NOT NULL REFERENCES Vehicles(vehicle_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, vehicle_id)
);

CREATE TABLE PermitTypes (
    type_id       SERIAL PRIMARY KEY,
    type_name     VARCHAR(50) NOT NULL UNIQUE,
    cost          DECIMAL(10,2) NOT NULL CHECK (cost >= 0),
    duration_days INT NOT NULL CHECK (duration_days > 0)
);

CREATE TABLE Permits (
    permit_id   SERIAL PRIMARY KEY,
    issue_date  DATE NOT NULL,
    expiry_date DATE NOT NULL,
    vehicle_id  INT NOT NULL REFERENCES Vehicles(vehicle_id)    ON DELETE CASCADE,
    type_id     INT NOT NULL REFERENCES PermitTypes(type_id)    ON DELETE RESTRICT,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    CHECK (expiry_date > issue_date)
);

CREATE TABLE Lots (
    lot_id   SERIAL PRIMARY KEY,
    lot_name VARCHAR(100) NOT NULL UNIQUE,
    location VARCHAR(255)
);

CREATE TABLE Spots (
    spot_id     SERIAL PRIMARY KEY,
    spot_number INT NOT NULL,
    spot_type   VARCHAR(50) NOT NULL,
    is_occupied BOOLEAN NOT NULL DEFAULT FALSE,
    lot_id      INT NOT NULL REFERENCES Lots(lot_id) ON DELETE CASCADE,
    UNIQUE (lot_id, spot_number)                    -- spot number unique per lot
);

CREATE TABLE Reservations (
    res_id     SERIAL PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time   TIMESTAMP NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'Confirmed'
               CHECK (status IN ('Confirmed','Completed','Cancelled')),
    user_id    INT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    spot_id    INT NOT NULL REFERENCES Spots(spot_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)                    -- Business Rule 3
);

CREATE TABLE Sensors (
    sensor_id    SERIAL PRIMARY KEY,
    sensor_model VARCHAR(100),
    spot_id      INT NOT NULL UNIQUE REFERENCES Spots(spot_id) ON DELETE CASCADE
);

CREATE TABLE SensorEvents (
    event_id        SERIAL PRIMARY KEY,
    event_type      VARCHAR(20) NOT NULL CHECK (event_type IN ('Arrival','Departure')),
    event_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sensor_id       INT NOT NULL REFERENCES Sensors(sensor_id) ON DELETE CASCADE
);

CREATE TABLE Tickets (
    ticket_id       SERIAL PRIMARY KEY,
    issue_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fine_amount     DECIMAL(10,2) NOT NULL CHECK (fine_amount > 0),  -- Business Rule 4
    status          VARCHAR(20) NOT NULL DEFAULT 'Issued'
                    CHECK (status IN ('Issued','Paid','Appealed','Voided')),
    vehicle_id      INT NOT NULL REFERENCES Vehicles(vehicle_id) ON DELETE CASCADE,
    spot_id         INT NOT NULL REFERENCES Spots(spot_id)       ON DELETE CASCADE
);

CREATE TABLE Payments (
    payment_id        SERIAL PRIMARY KEY,
    amount            DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    payment_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ticket_id         INT NOT NULL REFERENCES Tickets(ticket_id) ON DELETE CASCADE
);

-- =============================================================================
-- Stored routines
-- =============================================================================

-- issue_permit(): enforces "one active permit per vehicle" and derives the
-- expiry date from the permit type's duration rather than a hard-coded 180 days.
CREATE OR REPLACE FUNCTION issue_permit(v_id INT, t_id INT, start_date DATE)
RETURNS INT AS $$
DECLARE
    v_days   INT;
    v_permit INT;
BEGIN
    IF EXISTS (SELECT 1 FROM Permits
               WHERE vehicle_id = v_id AND expiry_date > start_date) THEN
        RAISE EXCEPTION 'Vehicle % already has an active permit.', v_id;
    END IF;

    SELECT duration_days INTO v_days FROM PermitTypes WHERE type_id = t_id;
    IF v_days IS NULL THEN
        RAISE EXCEPTION 'Permit type % does not exist.', t_id;
    END IF;

    INSERT INTO Permits (issue_date, expiry_date, vehicle_id, type_id)
    VALUES (start_date, start_date + (v_days || ' days')::interval, v_id, t_id)
    RETURNING permit_id INTO v_permit;

    RETURN v_permit;
END;
$$ LANGUAGE plpgsql;

-- Sensor occupancy trigger: flip Spots.is_occupied on Arrival/Departure.
CREATE OR REPLACE FUNCTION update_spot_occupancy()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE Spots
       SET is_occupied = (NEW.event_type = 'Arrival')
     WHERE spot_id = (SELECT spot_id FROM Sensors WHERE sensor_id = NEW.sensor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sensor_occupancy
AFTER INSERT ON SensorEvents
FOR EACH ROW EXECUTE FUNCTION update_spot_occupancy();

-- Auto-ticketing: issue a $50 fine for every occupied spot whose current
-- confirmed reservation belongs to a vehicle with NO valid permit.
-- Idempotent: skips vehicles/spots that already carry an open (Issued) ticket.
CREATE OR REPLACE PROCEDURE auto_generate_tickets()
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO Tickets (fine_amount, status, vehicle_id, spot_id)
    SELECT DISTINCT 50.00, 'Issued', uv.vehicle_id, s.spot_id
    FROM Spots s
    JOIN Reservations r
      ON s.spot_id = r.spot_id
     AND CURRENT_TIMESTAMP BETWEEN r.start_time AND r.end_time
     AND r.status = 'Confirmed'
    JOIN User_Vehicles uv ON r.user_id = uv.user_id
    WHERE s.is_occupied = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM Permits p
          WHERE p.vehicle_id = uv.vehicle_id
            AND CURRENT_DATE <= p.expiry_date
      )
      AND NOT EXISTS (                              -- de-dupe: no open ticket yet
          SELECT 1 FROM Tickets t
          WHERE t.vehicle_id = uv.vehicle_id
            AND t.spot_id = s.spot_id
            AND t.status = 'Issued'
      );
END;
$$;

-- Double-booking prevention. Two production fixes over the original:
--   1. pg_advisory_xact_lock(spot_id) serialises concurrent inserts for the
--      SAME spot, so the check-then-insert window can't be exploited by two
--      simultaneous transactions.
--   2. res_id <> NEW.res_id excludes the row itself, so UPDATEs of an existing
--      confirmed reservation no longer raise a false conflict.
CREATE OR REPLACE FUNCTION check_reservation_overlap()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status <> 'Confirmed' THEN
        RETURN NEW;                 -- only Confirmed rows hold a spot
    END IF;

    PERFORM pg_advisory_xact_lock(NEW.spot_id);

    IF EXISTS (
        SELECT 1 FROM Reservations
        WHERE spot_id = NEW.spot_id
          AND status  = 'Confirmed'
          AND res_id  <> COALESCE(NEW.res_id, -1)
          AND NEW.start_time < end_time
          AND NEW.end_time   > start_time
    ) THEN
        RAISE EXCEPTION
          'Double-booking rejected: spot % is already reserved for that window.',
          NEW.spot_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_double_booking
BEFORE INSERT OR UPDATE ON Reservations
FOR EACH ROW EXECUTE FUNCTION check_reservation_overlap();

-- =============================================================================
-- Views
-- =============================================================================
CREATE VIEW CurrentLotAvailability AS
SELECT l.lot_name, COUNT(s.spot_id) AS available_spots
FROM Lots l
JOIN Spots s ON l.lot_id = s.lot_id
WHERE s.is_occupied = FALSE
GROUP BY l.lot_name;

CREATE VIEW ActivePermitUserList AS
SELECT u.name, v.license_plate, p.expiry_date
FROM Users u
JOIN User_Vehicles uv ON u.user_id = uv.user_id
JOIN Vehicles v       ON uv.vehicle_id = v.vehicle_id
JOIN Permits p        ON v.vehicle_id = p.vehicle_id
WHERE p.expiry_date > CURRENT_DATE;
