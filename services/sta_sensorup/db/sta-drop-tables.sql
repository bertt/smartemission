--
-- PostgreSQL database dump
--


TRUNCATE TABLE observation RESTART IDENTITY CASCADE;

TRUNCATE TABLE sensor RESTART IDENTITY CASCADE;

TRUNCATE TABLE thing RESTART IDENTITY CASCADE;

TRUNCATE TABLE thing_location RESTART IDENTITY CASCADE;

TRUNCATE TABLE data_stream RESTART IDENTITY CASCADE;

TRUNCATE TABLE feature_of_interest RESTART IDENTITY CASCADE;

TRUNCATE TABLE observed_property RESTART IDENTITY CASCADE;

TRUNCATE TABLE location RESTART IDENTITY CASCADE;

TRUNCATE TABLE historical_location RESTART IDENTITY CASCADE;


DROP TABLE IF EXISTS observation CASCADE;

DROP TABLE IF EXISTS sensor CASCADE;

DROP TABLE IF EXISTS thing CASCADE;

DROP TABLE IF EXISTS thing_location CASCADE;

DROP TABLE IF EXISTS data_stream CASCADE;

DROP TABLE IF EXISTS feature_of_interest CASCADE;

DROP TABLE IF EXISTS observed_property CASCADE;

DROP TABLE IF EXISTS location CASCADE;

DROP TABLE IF EXISTS historical_location CASCADE;


DROP TABLE IF EXISTS observation RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS sensor RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS thing RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS thing_location RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS data_stream RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS feature_of_interest RESTART IDENTITY CASCADE;



DROP TABLE IF EXISTS observed_property RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS location RESTART IDENTITY CASCADE;

DROP TABLE IF EXISTS historical_location RESTART IDENTITY CASCADE;

