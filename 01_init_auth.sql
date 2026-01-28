CREATE DATABASE IF NOT EXISTS ttds_search_engine;

CREATE USER 'ttds_app'@'%' IDENTIFIED BY 'ttds#123';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON ttds_search_engine.* TO 'ttds_app'@'%';

FLUSH PRIVILEGES;