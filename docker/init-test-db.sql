-- Runs once when the postgres container's data volume is first initialized.
-- Gives the automated test suite its own database, separate from the one
-- the bot writes real (or AI-generated) data into, so a live bot session
-- and `pytest` never collide on the same rows.
CREATE DATABASE languagebot_test;
