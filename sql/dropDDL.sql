-- =============================================================================
-- dropDDL.sql  —  Reset script (drops everything the schema creates)
-- Views and functions/triggers fall with CASCADE on their tables.
-- =============================================================================
DROP TABLE IF EXISTS Payments      CASCADE;
DROP TABLE IF EXISTS Tickets       CASCADE;
DROP TABLE IF EXISTS SensorEvents  CASCADE;
DROP TABLE IF EXISTS Sensors       CASCADE;
DROP TABLE IF EXISTS Reservations  CASCADE;
DROP TABLE IF EXISTS Spots         CASCADE;
DROP TABLE IF EXISTS Lots          CASCADE;
DROP TABLE IF EXISTS Permits       CASCADE;
DROP TABLE IF EXISTS PermitTypes   CASCADE;
DROP TABLE IF EXISTS User_Vehicles CASCADE;
DROP TABLE IF EXISTS Vehicles      CASCADE;
DROP TABLE IF EXISTS Users         CASCADE;
DROP TABLE IF EXISTS Roles         CASCADE;

DROP FUNCTION IF EXISTS issue_permit(INT, INT, DATE)      CASCADE;
DROP FUNCTION IF EXISTS update_spot_occupancy()           CASCADE;
DROP FUNCTION IF EXISTS check_reservation_overlap()       CASCADE;
DROP PROCEDURE IF EXISTS auto_generate_tickets()          CASCADE;
