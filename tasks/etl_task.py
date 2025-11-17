import os
import duckdb
from datetime import datetime, timedelta
from prefect import task
from prefect.logging import get_run_logger




@task(retries=3, retry_delay_seconds=10)
def load_data_to_db(url: str,table:str , db_path: str) -> int:

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
        query = f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}')"
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


@task(retries=3, retry_delay_seconds=10)
def load_incremental_daily(url:str , table:str ,db_path:str):

    logger = get_run_logger()
    logger.info(f"Starting to do incremental load for table {table}")

    con = None
    try:
        print()
        con = duckdb.connect(db_path)
        today_date = datetime.now().date()
        query = f"SELECT MAX(visit_date) FROM {table}"
        latest_date_in_db = con.execute(query).fetchone()[0]
        differences = (today_date - latest_date_in_db) #to get how many days to iterate


        if differences <= 0:
            logger.info(f"No new data. Data in table {table} is up to date: {latest_date_in_db}")
            return


        for day in range(1,differences+1):
            date_to_load = latest_date_in_db + timedelta(days=day)
            day_url = url + date_to_load.strftime("%Y-%m-%d") + ".parquet"
            
            print(day)

    
    except Exception as e:
        print(e)
    finally:
        if con:
            con.close()
