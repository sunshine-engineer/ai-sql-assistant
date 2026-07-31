
-- ## Created new user , database and schema 
CREATE USER genai WITH PASSWORD 'genai';
CREATE DATABASE genai;
GRANT ALL PRIVILEGES ON DATABASE genai TO genai;

-- Grant full access to the public schema
GRANT ALL ON SCHEMA public TO genai;

-- Ensure the user owns all future tables/sequences created in this schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO genai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO genai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO genai;

CREATE SCHEMA IF NOT EXISTS genai;
-- 1. Allow the user to access the schema and create new objects in it
GRANT USAGE, CREATE ON SCHEMA genai TO genai;

-- 2. Grant full access to all existing tables and sequences
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA genai TO genai;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA genai TO genai;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA genai TO genai;

-- 3. Ensure the user automatically gets full access to FUTURE objects created in this schema
ALTER DEFAULT PRIVILEGES IN SCHEMA genai GRANT ALL ON TABLES TO genai;
ALTER DEFAULT PRIVILEGES IN SCHEMA genai GRANT ALL ON SEQUENCES TO genai;
ALTER DEFAULT PRIVILEGES IN SCHEMA genai GRANT ALL ON FUNCTIONS TO genai;   

GRANT pg_read_server_files TO genai;

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
COPY genai.nse_indices_daily
(
    trade_date,
    index_name,
    open_price,
    high_price,
    low_price,
    close_price,
    points_change,
    percent_change,
    volume_cr,
    turnover_rs_cr,
    pe_ratio,
    pb_ratio,
    dividend_yield
)
FROM '/tmp/dataset/AllIndices_02012026.csv'
DELIMITER ','
CSV HEADER;


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
