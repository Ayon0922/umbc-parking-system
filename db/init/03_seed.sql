-- =============================================================================
-- 03_seed.sql  —  Sample data (>= 10 rows per table)
-- =============================================================================
-- Fix vs. original loadAll.sql: the Payments block is now internally
-- consistent — every payment maps to a ticket whose status is 'Paid', and the
-- installments for each ticket sum EXACTLY to that ticket's fine_amount.
-- =============================================================================

-- 1. Roles
INSERT INTO Roles (role_name) VALUES
('Student'), ('Faculty'), ('Visitor'), ('Admin'),
('Staff'), ('Contractor'), ('Vendor'), ('VIP'), ('Maintenance'), ('Security');

-- 2. Users
INSERT INTO Users (name, email, role_id) VALUES
('Alice Smith',   'alice@umbc.edu',   1),
('Bob Lecturer',  'bob@umbc.edu',     2),
('Charlie Sneak', 'charlie@umbc.edu', 1),
('David Commuter','david@umbc.edu',   1),
('Eve Staff',     'eve@umbc.edu',     5),
('Frank Guest',   'frank@gmail.com',  3),
('Grace Admin',   'grace@umbc.edu',   4),
('Hank Vendor',   'hank@vendor.com',  7),
('Ivy Student',   'ivy@umbc.edu',     1),
('Jack Security', 'jack@umbc.edu',    10);

-- 3. Vehicles
INSERT INTO Vehicles (license_plate, make, model, color) VALUES
('ABC-1234','Toyota',   'Camry',   'Silver'),
('FAC-9999','BMW',      'X5',      'Black'),
('GUEST-11','Honda',    'Civic',   'White'),
('DEF-5678','Ford',     'Mustang', 'Red'),
('GHI-9012','Tesla',    'Model 3', 'Blue'),
('JKL-3456','Subaru',   'Outback', 'Green'),
('MNO-7890','Chevrolet','Express', 'White'),
('PQR-1234','Nissan',   'Altima',  'Gray'),
('STU-5678','Hyundai',  'Elantra', 'Black'),
('VWX-9012','Dodge',    'Charger', 'Black');

-- 4. User_Vehicles (M:N)
INSERT INTO User_Vehicles (user_id, vehicle_id) VALUES
(1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,7),(8,8),(9,9),(10,10);

-- 5. PermitTypes
INSERT INTO PermitTypes (type_name, cost, duration_days) VALUES
('Commuter Student', 150.00, 180),
('Premium Faculty',  300.00, 365),
('Resident Student', 200.00, 180),
('Standard Staff',   250.00, 365),
('Visitor Daily',     10.00,   1),
('Visitor Weekly',    40.00,   7),
('Vendor Annual',    500.00, 365),
('Motorcycle',        75.00, 180),
('Evening Only',     100.00, 180),
('Carpool',          120.00, 180);

-- 6. Permits
INSERT INTO Permits (issue_date, expiry_date, vehicle_id, type_id) VALUES
('2023-01-01','2023-06-01', 1, 1),   -- expired
('2026-05-01','2026-10-28', 1, 1),   -- active
('2025-08-01','2026-01-01', 4, 1),   -- expired
('2026-01-15','2026-07-15', 3, 1),   -- active
('2026-01-01','2026-12-31', 2, 2),   -- active
('2026-01-15','2026-07-15', 5, 1),   -- active
('2026-04-01','2026-04-08', 6, 6),   -- active (visitor weekly)
('2026-01-01','2026-12-31', 8, 7),   -- active (vendor)
('2026-01-15','2026-07-15', 9, 8),   -- active
('2026-01-01','2026-12-31',10, 4);   -- active

-- 7. Lots
INSERT INTO Lots (lot_name, location) VALUES
('Lot 4',               'North Campus'),
('Faculty Lot A',       'Administrative Drive'),
('Commons Garage',      'Central Campus'),
('Walker Avenue Garage','Residential Village'),
('RAC Lot',             'Retriever Activities Center'),
('Lot 1',               'South Campus'),
('Lot 3',               'Hilltop Circle'),
('Stadium Lot',         'Athletic Complex'),
('TRC Lot',             'Technology Research Center'),
('Visitor Pay Lot',     'Main Entrance');

-- 8. Spots
INSERT INTO Spots (spot_number, spot_type, is_occupied, lot_id) VALUES
(12, 'Student',  FALSE, 1),
(1,  'Faculty',  FALSE, 2),
(101,'Student',  FALSE, 3),
(102,'Student',  FALSE, 3),
(50, 'Resident', TRUE,  4),
(51, 'Resident', TRUE,  4),
(10, 'Student',  TRUE,  5),
(2,  'Visitor',  FALSE, 10),
(15, 'Student',  FALSE, 1),
(20, 'Faculty',  TRUE,  2);

-- 9. Reservations (no two Confirmed rows overlap on the same spot)
INSERT INTO Reservations (start_time, end_time, status, user_id, spot_id) VALUES
('2026-05-01 08:00','2026-05-01 10:00','Completed', 6, 8),
('2026-05-01 10:30','2026-05-01 12:30','Confirmed', 6, 8),
('2026-05-02 09:00','2026-05-02 17:00','Confirmed', 6, 8),
('2026-05-03 14:00','2026-05-03 16:00','Cancelled', 6, 8),
('2026-05-04 11:00','2026-05-04 13:00','Confirmed', 6, 8),
('2026-05-05 08:00','2026-05-05 10:00','Completed', 3, 1),
('2026-05-05 11:00','2026-05-05 15:00','Confirmed', 3, 1),
('2026-05-06 12:00','2026-05-06 14:00','Confirmed', 4, 2),
('2026-05-07 09:00','2026-05-07 11:00','Confirmed', 5, 5),
('2026-05-08 10:00','2026-05-08 12:00','Confirmed', 2, 6);

-- 10. Sensors (one per spot)
INSERT INTO Sensors (sensor_model, spot_id) VALUES
('HC-SR04-V1', 1), ('HC-SR04-V1', 2),
('HC-SR04-V2', 3), ('HC-SR04-V2', 4),
('LIDAR-X1',   5), ('LIDAR-X1',   6),
('LIDAR-X2',   7), ('LIDAR-X2',   8),
('MAG-SENSE-1',9), ('MAG-SENSE-1',10);

-- 11. SensorEvents
INSERT INTO SensorEvents (event_type, event_timestamp, sensor_id) VALUES
('Arrival',  '2026-04-01 08:00', 1),
('Departure','2026-04-01 17:00', 1),
('Arrival',  '2026-04-02 08:30', 2),
('Arrival',  '2026-04-02 07:45', 3),
('Departure','2026-04-02 18:00', 3),
('Arrival',  '2026-04-03 09:00', 5),
('Departure','2026-04-03 12:00', 5),
('Arrival',  '2026-04-04 10:00', 7),
('Arrival',  '2026-04-05 11:15', 9),
('Departure','2026-04-05 14:30', 9);

-- 12. Tickets  (Paid: #1,#4,#6,#8,#10 — payments below cover these exactly)
INSERT INTO Tickets (issue_timestamp, fine_amount, status, vehicle_id, spot_id) VALUES
('2026-03-01 10:00',  50.00, 'Paid',     3, 2),
('2026-03-05 14:30',  75.00, 'Issued',   4, 3),
('2026-03-10 09:15',  50.00, 'Appealed', 5, 2),
('2026-03-12 11:00', 100.00, 'Paid',     8, 4),
('2026-03-15 16:45',  50.00, 'Issued',   9, 3),
('2026-03-20 08:30',  25.00, 'Paid',     3, 1),
('2026-03-22 13:20',  50.00, 'Issued',   6, 2),
('2026-03-25 10:00', 150.00, 'Paid',     1, 7),
('2026-03-28 15:10',  50.00, 'Appealed', 4, 3),
('2026-04-01 09:05',  75.00, 'Paid',     5, 3);

-- 13. Payments (installments sum EXACTLY to each Paid ticket's fine_amount)
INSERT INTO Payments (amount, payment_timestamp, ticket_id) VALUES
( 30.00, '2026-03-02 09:00', 1),   -- ticket 1: 30 + 20 = 50
( 20.00, '2026-03-03 09:00', 1),
( 60.00, '2026-03-13 09:00', 4),   -- ticket 4: 60 + 40 = 100
( 40.00, '2026-03-14 10:00', 4),
( 25.00, '2026-03-21 14:00', 6),   -- ticket 6: 25
( 50.00, '2026-03-26 11:30', 8),   -- ticket 8: 50 + 50 + 50 = 150
( 50.00, '2026-03-27 11:30', 8),
( 50.00, '2026-03-28 11:30', 8),
( 50.00, '2026-04-03 10:00',10),   -- ticket 10: 50 + 25 = 75
( 25.00, '2026-04-04 10:00',10);
