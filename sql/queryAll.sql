-- =============================================================================
-- queryAll.sql  —  10 course-level queries for the UMBC Parking Management System
-- =============================================================================

-- 1. Simple join: users and their roles
SELECT u.name, r.role_name
FROM Users u
JOIN Roles r ON u.role_id = r.role_id
ORDER BY u.name;

-- 2. Aggregation: vehicles registered per user
SELECT u.name, COUNT(uv.vehicle_id) AS vehicle_count
FROM Users u
LEFT JOIN User_Vehicles uv ON u.user_id = uv.user_id
GROUP BY u.name
ORDER BY vehicle_count DESC, u.name;

-- 3. Filter + join: active permits for Student-role users
SELECT v.license_plate, p.expiry_date
FROM Permits p
JOIN Vehicles v      ON p.vehicle_id  = v.vehicle_id
JOIN User_Vehicles uv ON v.vehicle_id = uv.vehicle_id
JOIN Users u         ON uv.user_id    = u.user_id
JOIN Roles r         ON u.role_id     = r.role_id
WHERE r.role_name = 'Student' AND p.expiry_date > CURRENT_DATE;

-- 4. Subquery: lots with no occupied spots
SELECT lot_name FROM Lots
WHERE lot_id NOT IN (SELECT lot_id FROM Spots WHERE is_occupied = TRUE);

-- 5. Set operation: users who have both a permit and a ticket
SELECT DISTINCT u.user_id, u.name FROM Users u
JOIN User_Vehicles uv ON u.user_id = uv.user_id
JOIN Permits p        ON uv.vehicle_id = p.vehicle_id
INTERSECT
SELECT DISTINCT u.user_id, u.name FROM Users u
JOIN User_Vehicles uv ON u.user_id = uv.user_id
JOIN Tickets t        ON uv.vehicle_id = t.vehicle_id;

-- 6. Complex join: full sensor-event history for 'Lot 4'
SELECT l.lot_name, s.spot_number, se.event_type, se.event_timestamp
FROM Lots l
JOIN Spots s        ON l.lot_id = s.lot_id
JOIN Sensors sn     ON s.spot_id = sn.spot_id
JOIN SensorEvents se ON sn.sensor_id = se.sensor_id
WHERE l.lot_name = 'Lot 4'
ORDER BY se.event_timestamp DESC;

-- 7. GROUP BY / HAVING: lots with more than 1 available spot
--    (thresh set to 1 so it returns rows with the sample data — raise for prod)
SELECT l.lot_name, COUNT(s.spot_id) AS available_count
FROM Lots l
JOIN Spots s ON l.lot_id = s.lot_id
WHERE s.is_occupied = FALSE
GROUP BY l.lot_name
HAVING COUNT(s.spot_id) > 1;

-- 8. EXPENSIVE #1: multi-way join for detailed ticket reporting
EXPLAIN ANALYZE
SELECT u.name, v.license_plate, t.fine_amount, l.lot_name, t.issue_timestamp
FROM Users u
JOIN User_Vehicles uv ON u.user_id = uv.user_id
JOIN Vehicles v       ON uv.vehicle_id = v.vehicle_id
JOIN Tickets t        ON v.vehicle_id = t.vehicle_id
JOIN Spots s          ON t.spot_id = s.spot_id
JOIN Lots l           ON s.lot_id = l.lot_id
WHERE t.status = 'Issued';

-- 9. EXPENSIVE #2: reservation-overlap self-join (double-booking detector)
EXPLAIN ANALYZE
SELECT r1.res_id AS res_a, r2.res_id AS res_b, r1.spot_id
FROM Reservations r1
JOIN Reservations r2 ON r1.spot_id = r2.spot_id
WHERE r1.res_id < r2.res_id          -- each conflicting pair once, no self-match
  AND r1.status = 'Confirmed' AND r2.status = 'Confirmed'
  AND r1.start_time < r2.end_time
  AND r1.end_time   > r2.start_time;

-- 10. EXPENSIVE #3: PERMIT revenue per permit type
--     FIX: the original summed fine PAYMENTS grouped by permit type, which is
--     fine collection, not permit revenue. Permit revenue = number of permits
--     sold of a type * that type's cost.
EXPLAIN ANALYZE
SELECT pt.type_name,
       COUNT(pr.permit_id)        AS permits_sold,
       SUM(pt.cost)               AS permit_revenue
FROM PermitTypes pt
JOIN Permits pr ON pt.type_id = pr.type_id
GROUP BY pt.type_name
ORDER BY permit_revenue DESC;

-- 10b. (Companion, correctly labelled) FINE revenue actually collected,
--      broken down by the permit type the fined vehicle holds.
SELECT pt.type_name, SUM(pay.amount) AS fines_collected
FROM PermitTypes pt
JOIN Permits pr  ON pt.type_id  = pr.type_id
JOIN Tickets t   ON pr.vehicle_id = t.vehicle_id
JOIN Payments pay ON t.ticket_id = pay.ticket_id
GROUP BY pt.type_name
ORDER BY fines_collected DESC;
