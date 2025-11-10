
--for table historical and daily
SELECT h.inst_code , ic.state,ic.hospital , count(*)
FROM main.inst_code ic 
LEFT JOIN main.historical h on h.inst_code = ic.inst_code 
WHERE h.visit_date = DATE '2025-11-01'
GROUP BY h.inst_code ,ic.state ,ic.hospital ;
--LEFT JOIN main.malaysia_states ms ON ic.state = ms.shapeName ; 

DELETE FROM main.historical 
WHERE visit_date = DATE '2025-10-29';

SELECT count(*) FROM main.historical h;

SELECT max(visit_date) FROM main.historical h;

SELECT COUNT(*) FROM main.historical h ;

SELECT 
    MIN(EXTRACT(YEAR FROM visit_date)) AS earliest_year,
    MAX(EXTRACT(YEAR FROM visit_date)) AS latest_year,
    COUNT(DISTINCT EXTRACT(YEAR FROM visit_date)) AS unique_years
FROM main.historical h ;


--SELECT spesific year
SELECT count(*)
FROM main.historical
WHERE visit_date = DATE '2025-10-30';

SELECT 
    MIN(EXTRACT(MONTH FROM visit_date)) AS earliest_month,
    MAX(EXTRACT(MONTH FROM visit_date)) AS latest_month,
    COUNT(DISTINCT EXTRACT(MONTH FROM visit_date)) AS unique_months
FROM main.daily d;

SELECT MIN(visit_date) , MAX(visit_date) 
FROM main.historical h;




SELECT count(DISTINCT inst_code) FROM main.historical h ;


--to count distinct value for each column in table historical
SELECT 
	count(DISTINCT donation_type) AS  count_donation_type ,
	count(DISTINCT donation_location) AS  count_donation_location,
	count(DISTINCT classification_id) AS  count_classification_id,
	count(DISTINCT blood_group) AS  count_blood_group
FROM main.historical h ;

--show unique value for each column
SELECT DISTINCT donation_type FROM main.historical h ORDER BY donation_type ;
SELECT DISTINCT donation_location FROM main.historical h ;
SELECT DISTINCT classification_id FROM main.historical h ORDER BY classification_id ;
SELECT DISTINCT blood_group FROM main.historical h ORDER BY blood_group ;


--for table rate
SELECT DISTINCT race FROM main.donorrate d  ORDER BY race  ;
SELECT DISTINCT gender FROM main.donorrate d ORDER BY gender ;
SELECT min(birth_date) , max(birth_date) ,count(DISTINCT birth_date) FROM main.donorrate d ;

--for table retention
SELECT min(birth_date) , max(birth_date) ,count(DISTINCT birth_date) FROM main.retention r ;



SELECT max(latest) FROM main.donorrate r;




-- Create a sample table
CREATE TABLE locations (
    name VARCHAR,
    latitude DOUBLE,
    longitude DOUBLE
);

-- Insert your location
INSERT INTO locations (name, latitude, longitude)
VALUES ('Yong Peng', );

-- Query the table and create the geometry
SELECT 
    name,
    ST_Point(longitude, latitude) AS geom
FROM locations;

INSTALL spatial;
LOAD spatial;

CREATE TABLE my_locations (
    latitude DOUBLE,
    longitude DOUBLE
);

INSERT INTO my_locations (latitude, longitude) VALUES
(1.463136148, 103.7468032),
(6.149091168, 100.4065559),
(6.125448302, 102.2463128),
(2.217374167, 102.2616891),
(2.709977349, 101.9453237),
(3.800909762, 103.3417734),
(3.453300959, 102.4537439),
(5.394363705, 100.4075842),
(5.417555904, 100.3106202),
(4.604132976, 101.0907771),
(4.851211566, 100.7374523),
(4.185841497, 100.6627478),
(3.020305789, 101.4406719),
(5.324098277, 103.1511672),
(5.968147463, 116.096077),
(5.859199163, 118.1036425),
(4.250073577, 117.8812042),
(1.544930993, 110.340032),
(4.37458904, 114.0001665),
(2.296717562, 111.8920928),
(3.173280168, 101.7069171),
(1.837805527, 102.9415869);



SELECT ST_Point(longitude, latitude) AS map_point
FROM my_locations;




INSTALL httpfs;
LOAD spatial;
LOAD httpfs;

CREATE TABLE malaysia_states AS 
SELECT * FROM ST_Read('https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MYS/ADM1/geoBoundaries-MYS-ADM1_simplified.geojson');

SELECT * FROM malaysia_states;

SELECT 
    ic.inst_code, 
    ic.state, 
    ic.hospital, 
    COUNT(h.visit_date) AS visit_count
FROM 
    main.inst_code ic
LEFT JOIN 
    main.historical h ON ic.inst_code = h.inst_code 
                     AND YEAR(h.visit_date) = 2025
GROUP BY 
    ic.inst_code, 
    ic.state, 
    ic.hospital;