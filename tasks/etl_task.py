import duckdb
from datetime import datetime, timedelta
from prefect import task
from prefect.logging import get_run_logger




@task(retries=3, retry_delay_seconds=10)
def load_transformed_retention_to_db(url: str,table:str , db_path: str) -> int:
    

    logger = get_run_logger()
    logger.info(f"Starting to delete table {table} and replace it with new table {table}")
    
    con = None

    try:
        con = duckdb.connect(db_path)

        # counting how many rows are there before replacing new one
        query = f"SELECT COUNT(*) FROM {table}"
        count_before = con.execute(query).fetchone()[0]

        # Delete and insert new one
        logger.info(f"Starting to delete and load new data into {table} table...")
        query = f"""
                    create or replace table {table} as
                    select *, 
                    lag(visit_date,1,visit_date) over(w) as previous_visit,
                    lead(visit_date,1,visit_date) over(w) as next_visit,
                    date_diff('day', LAG(visit_date) OVER w, visit_date) AS days_diff,
                    case
                        when lag(visit_date) over w is null then 'First Visit'
                        when lead(visit_date) over w is null then 'Last Visit'
                        else 'Returning'
                    end as visit_status,
                    row_number() over (partition by donor_id order by visit_date) as nth_visit,
                    year(visit_date) - birth_date as age
                    from read_parquet('{url}')
                    window w as (partition by donor_id order by visit_date)
                    order by donor_id,visit_date 
                 """
        con.execute(query)
        logger.info(f"Successfully loaded new data into {table} table.")

        query = f"SELECT COUNT(*) FROM {table}"
        count_after = con.execute(query).fetchone()[0]

        increment = count_after - count_before

        return increment

    except Exception as e:
        logger.error(f"Failed to load on table {table} because: {e}")
        raise
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")

@task(retries=3, retry_delay_seconds=10)
def load_transformed_donorrate_to_db(url: str,table:str , db_path: str) -> int:

    logger = get_run_logger()
    logger.info(f"Starting to delete table {table} and replace it with new table {table}")
    
    con = None

    try:
        con = duckdb.connect(db_path)

        # counting how many rows are there before replacing new one
        query = f"SELECT COUNT(*) FROM {table}"
        count_before = con.execute(query).fetchone()[0]

        # Delete and insert new one
        logger.info(f"Starting to delete and load new data into {table} table...")
        query = f""" create or replace table {table} as select *,year(latest) - birth_date as age from read_parquet('{url}') order by latest desc """
        con.execute(query)
        logger.info(f"Successfully loaded new data into {table} table.")

        query = f"SELECT COUNT(*) FROM {table}"
        count_after = con.execute(query).fetchone()[0]

        increment = count_after - count_before

        return increment

    except Exception as e:
        logger.error(f"Failed to load on table {table} because: {e}")
        raise
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")

@task(retries=3, retry_delay_seconds=10)
def load_incremental_daily(url:str , table:str ,db_path:str) -> dict: 

    logger = get_run_logger()
    logger.info(f"Starting to do incremental load for table {table}")

    con = None
    try:
        con = duckdb.connect(db_path)
        today_date = datetime.now().date()
        
        latest_date_in_db = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()[0]
        total_data_before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        
        latest_successful_date = None 
        differences = (today_date - latest_date_in_db).days 

        if differences <= 0:
            logger.info(f"No new data or DB is ahead. Latest: {latest_date_in_db}")
            return {"new_rows": 0, "latest_date": latest_date_in_db}

        for day in range(1, differences + 1):
            date_to_load = latest_date_in_db + timedelta(days=day)
            day_url = f"{url}{date_to_load.strftime('%Y-%m-%d')}.parquet"

            query = f"""INSERT INTO {table} 
                        SELECT 
                            inst_code,
                            CAST(visit_date AS DATE) as visit_date,
                            CAST(NULLIF(previous_visit, '1800-08-10') AS DATE) as previous_visit,
                            (CAST(visit_date AS DATE) - CAST(NULLIF(previous_visit, '1800-08-10') AS DATE)) as days_since_last,
                            CASE WHEN previous_visit = '1800-08-10' THEN TRUE ELSE FALSE END as is_first_visit,
                            donation_type,
                            donation_location,
                            classification_id,
                            blood_group
                        FROM read_parquet('{day_url}')"""
            
            try:
                con.execute(query)
                logger.info(f"Successfully loaded: {date_to_load}")
                latest_successful_date = date_to_load
            except duckdb.IOException:
                logger.warning(f"Data for {date_to_load} not available yet.")
                break
            except Exception as e:
                logger.error(f"Failed at {date_to_load}: {e}")
                break

        if latest_successful_date:
            total_data_after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            final_max_date = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()[0]
            total_new_data = total_data_after - total_data_before
            return total_new_data, final_max_date
        else:
            return 0, latest_date_in_db

    except Exception as e:
        logger.error(f"Daily incremental load failed: {e}")
        raise # Re-raise so Prefect knows the task failed
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")
