
--for table historical and daily

SELECT * FROM main.historical h LIMIT 10;

SELECT COUNT(*) FROM main.historical h ;

SELECT 
    MIN(EXTRACT(YEAR FROM visit_date)) AS earliest_year,
    MAX(EXTRACT(YEAR FROM visit_date)) AS latest_year,
    COUNT(DISTINCT EXTRACT(YEAR FROM visit_date)) AS unique_years
FROM main.daily d;

SELECT 
    MIN(EXTRACT(MONTH FROM visit_date)) AS earliest_month,
    MAX(EXTRACT(MONTH FROM visit_date)) AS latest_month,
    COUNT(DISTINCT EXTRACT(MONTH FROM visit_date)) AS unique_months
FROM main.daily d;

SELECT MIN(visit_date) , MAX(visit_date) 
FROM main.historical h 




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
SELECT DISTINCT race FROM main.rate r ORDER BY race  ;
SELECT DISTINCT gender FROM main.rate r ORDER BY gender ;
SELECT min(birth_date) , max(birth_date) ,count(DISTINCT birth_date) FROM main.rate r ;

--for table retention
SELECT min(birth_date) , max(birth_date) ,count(DISTINCT birth_date) FROM main.retention r ;