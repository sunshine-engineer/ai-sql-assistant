\set ON_ERROR_STOP on
-- Bootstrap only: run as the database administrator, never as the assistant.
-- Passwords are supplied interactively through psql, not stored in Git.
CREATE ROLE genai_loader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE genai_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password genai_loader
\password genai_reader
CREATE DATABASE genai OWNER genai_loader;
\connect genai
REVOKE ALL ON DATABASE genai FROM PUBLIC;
GRANT CONNECT ON DATABASE genai TO genai_loader, genai_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA genai AUTHORIZATION genai_loader;
GRANT USAGE ON SCHEMA genai TO genai_reader;
ALTER ROLE genai_reader SET default_transaction_read_only = on;
ALTER ROLE genai_reader SET statement_timeout = '5s';
ALTER ROLE genai_reader SET search_path = genai;
-- These grants apply only to objects created by the loader.
ALTER DEFAULT PRIVILEGES FOR ROLE genai_loader IN SCHEMA genai
    GRANT SELECT ON TABLES TO genai_reader;
-- No server-file role, write privileges, function grants, or loader membership.
SET ROLE genai_loader;

-- ## Loading data from NSE all indices

CREATE TABLE IF NOT EXISTS genai.nse_indices_daily
(
    id                  BIGSERIAL PRIMARY KEY,

    trade_date          DATE NOT NULL,

    index_name          VARCHAR(100) NOT NULL,

    open_price          NUMERIC(12,2),
    high_price          NUMERIC(12,2),
    low_price           NUMERIC(12,2),
    close_price         NUMERIC(12,2),

    points_change       NUMERIC(12,2),
    percent_change      NUMERIC(10,4),

    volume_cr           NUMERIC(15,2),
    turnover_rs_cr      NUMERIC(18,2),

    pe_ratio            NUMERIC(10,2),
    pb_ratio            NUMERIC(10,2),
    dividend_yield      NUMERIC(10,2),

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_index_date
        UNIQUE (trade_date, index_name)
);


CREATE INDEX idx_nse_indices_date
ON genai.nse_indices_daily(trade_date);

CREATE INDEX idx_nse_indices_name
ON genai.nse_indices_daily(index_name);

CREATE INDEX idx_nse_indices_date_name
ON genai.nse_indices_daily(trade_date, index_name);

SELECT id, trade_date, index_name, open_price, high_price, low_price, close_price, points_change, percent_change, volume_cr, turnover_rs_cr, pe_ratio, pb_ratio, dividend_yield, created_at
FROM genai.nse_indices_daily;

-- source >> https://www.bseindia.com/indices/indexarchivedata
-- Run psql from the repository root. Client-side loading needs no server-file role.
\copy genai.nse_indices_daily (trade_date,index_name,open_price,high_price,low_price,close_price,points_change,percent_change,volume_cr,turnover_rs_cr,pe_ratio,pb_ratio,dividend_yield) FROM 'dataset/AllIndices_02012026.csv' CSV HEADER
GRANT SELECT ON ALL TABLES IN SCHEMA genai TO genai_reader;
RESET ROLE;

-- Example Queries
-- Latest NIFTY 50
SELECT *
FROM genai.nse_indices_daily
WHERE index_name='NIFTY 50'
ORDER BY trade_date DESC
LIMIT 10;

-- Highest Closing Value
SELECT
    trade_date,
    index_name,
    close_price
FROM genai.nse_indices_daily
ORDER BY close_price DESC;

-- Daily Percentage Change
SELECT
    trade_date,
    percent_change
FROM genai.nse_indices_daily
WHERE index_name='NIFTY 50'
ORDER BY trade_date;

-- Average Close
SELECT
    index_name,
    AVG(close_price) AS avg_close
FROM genai.nse_indices_daily
GROUP BY index_name;
