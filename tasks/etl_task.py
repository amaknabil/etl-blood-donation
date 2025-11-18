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
            logger.info("Database connection closed.")


@task(retries=3, retry_delay_seconds=10)
def load_incremental_daily(url:str , table:str ,db_path:str) -> int:

    logger = get_run_logger()
    logger.info(f"Starting to do incremental load for table {table}")

    con = None
    try:
        print()
        con = duckdb.connect(db_path)
        today_date = datetime.now().date()
        query = f"SELECT MAX(visit_date) FROM {table}"

        latest_successful_date = None # this variable is a flag for me to know what date is successful
        latest_date_in_db = con.execute(query).fetchone()[0]
        differences = (today_date - latest_date_in_db).days #to get how many days to iterate


        if differences == 0:
            logger.info(f"No new data. Data in table {table} is up to date: {latest_date_in_db}")
            return 0
        elif differences < 0:
            logger.info(f"Data in DB is further date than latest from API, please check with Thevesh")
            return 0
        
        query = f"SELECT COUNT(*) FROM {table}"
        total_data_before_insert = con.execute(query).fetchone()[0]

        for day in range(1,differences+1):
            date_to_load = latest_date_in_db + timedelta(days=day)
            day_url = url + date_to_load.strftime("%Y-%m-%d") + ".parquet"

            query = f"INSERT INTO {table} SELECT * FROM read_parquet('{day_url}')"
            logger.info(f"Starting to add new data for date: {date_to_load}")

            try:
                con.execute(query)
                logger.info(f"Successfully loaded new data for date: {date_to_load}")
                latest_successful_date = date_to_load
            except duckdb.IOException:
                logger.warning(f"Data for date {date_to_load} is not available yet.")
                break
            except Exception as e:
                logger.error(f"Failed to load data for date : {date_to_load} \n because : {e} ")
                break

        if latest_successful_date:
            logger.info(f"Successfully loaded new data up to {latest_successful_date}")

            query = f"SELECT COUNT(*) FROM {table}"
            total_data_after_insert = con.execute(query).fetchone()[0]
            total_new_data = total_data_after_insert - total_data_before_insert
            return total_new_data
        else:
            logger.info(f"No new data. Latest date in table {table} is at {latest_date_in_db}")
            return 0

    except Exception as e:
        logger.error(f"Daily incremental load failed because: {e}")
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")
