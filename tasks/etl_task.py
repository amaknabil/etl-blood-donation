import duckdb
from datetime import datetime, timedelta
from prefect import task
from prefect.logging import get_run_logger
import httpx



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

@task( retries=95, retry_delay_seconds=900, task_run_name="Check Availability {table}'s Data1")
def check_available_daily_data(base_url: str, db_path: str, table: str,config):
    logger = get_run_logger()
    con = None
    
    try:
        con = duckdb.connect(db_path,config=config)
        latest_date_in_db = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()[0]
        yesterday = datetime.now().date() - timedelta(days=1)
        
        if latest_date_in_db >= yesterday:
            logger.info("Database is already up to date (up to yesterday).")
            return True

        days_to_check = (yesterday - latest_date_in_db).days
        
        logger.info(f"Missing {days_to_check} days of data. Checking availability...")

        for day in range(1, days_to_check + 1):
            date_to_load = latest_date_in_db + timedelta(days=day)
            formatted_date = date_to_load.strftime('%Y-%m-%d')
            target_url = f"{base_url.rstrip('/')}/{formatted_date}.parquet"
            
            logger.info(f"Probing: {target_url}")
            
            response = httpx.head(target_url, follow_redirects=True)
            
            if response.status_code == 200:
                logger.info(f"Found: {formatted_date}")
                continue 
            elif response.status_code == 404:
                raise ValueError(f"Required data for {formatted_date} is missing (404).")
            else:
                raise Exception(f"Server error {response.status_code} for {formatted_date}")
        return True

    except Exception as e:
        logger.error(f"Availability check failed: {e}")
        raise 
    finally:
        if con:
            con.close()

@task(retries=95, retry_delay_seconds=900,task_run_name="Check Availability {table}'s Data2")
def check_available_other_data(url: str, db_path: str, table: str,config):
    logger = get_run_logger()
    con = None

    try:
        con = duckdb.connect(db_path,config=config)
        count_before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        query_remote = f"SELECT COUNT(*) FROM read_parquet('{url}')"
        count_after = con.execute(query_remote).fetchone()[0]

        logger.info(f"Local count: {count_before} | Remote count: {count_after}")

        if count_after > count_before:
            logger.info("New data detected. Proceeding...")
            return True
        else:
            raise ValueError(
                f"No new rows found. Remote ({count_after}) is not greater "
                f"than Local ({count_before}) at {datetime.now()}."
            )
    except Exception as e:
        logger.error(f"Data verification failed: {e}")
        raise 
    finally:
        if con:
            con.close()


# @task(retries=3, retry_delay_seconds=10)
# def load_incremental_daily(url:str , table:str ,db_path:str) -> dict: 

#     logger = get_run_logger()
#     logger.info(f"Starting to do incremental load for table {table}")

#     con = None
#     try:
#         con = duckdb.connect(db_path)
#         today_date = datetime.now().date()
        
#         latest_date_in_db = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()[0]
#         total_data_before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        
#         latest_successful_date = None 
#         differences = (today_date - latest_date_in_db).days 

#         if differences <= 0:
#             logger.info(f"No new data or DB is ahead. Latest: {latest_date_in_db}")
#             return {"new_rows": 0, "latest_date": latest_date_in_db}

#         for day in range(1, differences + 1):
#             date_to_load = latest_date_in_db + timedelta(days=day)
#             day_url = f"{url}{date_to_load.strftime('%Y-%m-%d')}.parquet"

#             query = f"""INSERT INTO {table} 
#                         SELECT 
#                             inst_code,
#                             CAST(visit_date AS DATE) as visit_date,
#                             CAST(NULLIF(previous_visit, '1800-08-10') AS DATE) as previous_visit,
#                             (CAST(visit_date AS DATE) - CAST(NULLIF(previous_visit, '1800-08-10') AS DATE)) as days_since_last,
#                             CASE WHEN previous_visit = '1800-08-10' THEN TRUE ELSE FALSE END as is_first_visit,
#                             donation_type,
#                             donation_location,
#                             classification_id,
#                             blood_group
#                         FROM read_parquet('{day_url}')"""
            
#             try:
#                 con.execute(query)
#                 logger.info(f"Successfully loaded: {date_to_load}")
#                 latest_successful_date = date_to_load
#             except duckdb.IOException:
#                 logger.warning(f"Data for {date_to_load} not available yet.")
#                 break
#             except Exception as e:
#                 logger.error(f"Failed at {date_to_load}: {e}")
#                 break

#         if latest_successful_date:
#             total_data_after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
#             final_max_date = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()[0]
#             total_new_data = total_data_after - total_data_before
#             return total_new_data, final_max_date
#         else:
#             return 0, latest_date_in_db

#     except Exception as e:
#         logger.error(f"Daily incremental load failed: {e}")
#         raise # Re-raise so Prefect knows the task failed
#     finally:
#         if con:
#             con.close()
#             logger.info("Database connection closed.")


@task(retries=3, retry_delay_seconds=10)
def load_data_to_db_donorrate(url: str, table: str, db_path: str,config) -> int:
    con = None
    logger = get_run_logger() # Assuming this is from Prefect or similar
    
    try:
        con = duckdb.connect(db_path,config=config)
    
        if url.startswith("http") or url.startswith("s3"):
            con.execute("INSTALL httpfs; LOAD httpfs;")

        table_exists = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", 
            [table]
        ).fetchone()[0] > 0

        if table_exists:
            count_before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        else:
            count_before = 0
            logger.info(f"Table '{table}' does not exist yet. Creating new.")

        query = f"CREATE OR REPLACE TABLE {table} AS SELECT *, year(latest) - birth_date as age  FROM read_parquet('{url}')"
        con.execute(query)
        count_after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        diff = count_after - count_before
        
        logger.info(f"{table} refreshed. Row count changed by {diff} (From {count_before} to {count_after})")
        return diff

    except Exception as e:
        logger.error(f"Load failed: {e}")
        raise
    finally:
        if con:
            con.close()
        
@task(retries=3, retry_delay_seconds=10, task_run_name="Load {table} Data")
def load_data_to_db(url: str, table: str, db_path: str,config) -> tuple:
    logger = get_run_logger()
    con = None
    
    try:
        con = duckdb.connect(db_path,config=config)
        con.execute("INSTALL httpfs; LOAD httpfs;")

        date_col = "visit_date" if table in ["historical", "retention"] else "latest"
        
        latest_date_in_db = con.execute(f"SELECT MAX({date_col}) FROM {table}").fetchone()[0]
        count_before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        
        target_date = (datetime.now() - timedelta(days=1)).date()
        differences = (target_date - latest_date_in_db).days 

        if differences <= 0:
            logger.info(f"Table {table} is already up to date.")
            return  0,  latest_date_in_db

        latest_successful_date = latest_date_in_db
        
        for day in range(1, differences + 1):
            date_to_load = latest_date_in_db + timedelta(days=day)
            formatted_date = date_to_load.strftime('%Y-%m-%d')
            
            # 4. Define SQL based on Table Type
            if table == "historical":
                # Detailed logic for historical table
                query = f"""
                    INSERT INTO {table}
                    SELECT 
                        inst_code,
                        CAST(visit_date AS DATE) as visit_date,
                        CAST(NULLIF(previous_visit, '1800-08-10') AS DATE) as previous_visit,
                        (CAST(visit_date AS DATE) - CAST(NULLIF(previous_visit, '1800-08-10') AS DATE)) as days_since_last,
                        CASE WHEN previous_visit = '1800-08-10' THEN TRUE ELSE FALSE END as is_first_visit,
                        donation_type, donation_location, classification_id, blood_group
                    FROM read_parquet('{url}{formatted_date}.parquet')
                    WHERE visit_date = '{formatted_date}'
                """
            elif table == "retention":
                # Simple pass-through for retention
                query = f"INSERT INTO {table} SELECT * FROM read_parquet('{url}') where visit_date = '{formatted_date}'"
            else:
                # Logic for donorrate or other simple tables
                query = f"""
                    INSERT INTO {table} 
                    SELECT *, year(latest) - birth_date as age 
                    FROM read_parquet('{url}') 
                    WHERE latest = '{formatted_date}'
                """

            try:
                con.execute(query)
                logger.info(f"Loaded {table} for {formatted_date}")
                latest_successful_date = date_to_load
            except duckdb.IOException:
                logger.warning(f"File not found for {formatted_date}. Stopping for today.")
                break 

        # 5. Calculate Final Statistics
        count_after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        increment = count_after - count_before

        logger.info(f"increment is {increment}, before is {count_before}, after is { count_after} for table {table} ")
        
        return  increment,latest_successful_date
        
    except Exception as e:
        logger.error(f"Load failed for {table}: {e}")
        raise
    finally:
        if con:
            con.close()

@task(retries=3, retry_delay_seconds=10)
def get_latest_date_in_db(db_path:str,table: str,config):
    con =None
    try:
        with duckdb.connect(db_path, read_only=True,config=config) as con:

            query = f'SELECT MAX(visit_date) FROM "{table}"'
            result = con.execute(query).fetchone()
            return result[0] if result else None
    except duckdb.Error as e:
            print(f"Database error: {e}")
            return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


