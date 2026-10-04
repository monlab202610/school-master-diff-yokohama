-- Run from the package root with sqlite3 :memory: < examples/lookup.sql
-- The tables live only in memory. All CSV columns are imported as TEXT.
.mode csv
.import data/before.csv before_school
.import data/after.csv after_school
.headers on
.mode column
SELECT a.school_code, b.school_name AS before_name, a.school_name AS after_name,
       b.branch_status AS before_status, a.branch_status AS after_status,
       b.attribute_retired_date AS before_retired, a.attribute_retired_date AS after_retired
FROM after_school a JOIN before_school b USING(school_code)
WHERE a.school_name <> b.school_name OR a.branch_status <> b.branch_status
   OR a.attribute_retired_date <> b.attribute_retired_date
ORDER BY a.school_code;

SELECT school_code, school_name
FROM after_school
WHERE school_code NOT IN (SELECT school_code FROM before_school)
ORDER BY school_code;
