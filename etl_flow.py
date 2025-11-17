import os
import duckdb
from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta

# Prefect imports
from prefect import flow, task
from prefect.logging import get_run_logger
# The old Deployment imports are no longer needed
# from prefect.deployments import Deployment
# from prefect.server.schemas.schedules import CronSchedule

# Telegram/Plotting Imports
import telebot
import pandas as pd
import matplotlib.pyplot as plt
import io

# --- Task Definitions ---

@task(retries=3, retry_delay_seconds=10)
def load_data_to_db(url: str, table: str, db_path: str):
    """
    Task to completely replace a table in DuckDB from a Parquet URL.
    """
    logger = get_run_logger()
    logger.info(f"Starting incremental load for table: {table}")
    
    con = None
    try:
        con = duckdb.connect(db_path)
        logger.info(f"1 - Deleting data from table {table}....")
        con.execute(f"DELETE FROM {table}")
        con.commit()
        
        query = f"INSERT INTO {table} SELECT * FROM read_parquet('{url}')"
        logger.info(f"2 - Starting to load new data into {table} table...")
        con.execute(query)
        logger.info(f"Successfully loaded new data into {table} table.")
        
    except Exception as e:
        logger.error(f"Failed to load on table {table} because: {e}")
        raise
    finally:
        if con:
            con.close()

@task(retries=3, retry_delay_seconds=10)
def load_incremental_daily(url_prefix: str, table: str, db_path: str):
    """
    Task to load new daily Parquet files into the 'historical' table.
    """
    logger = get_run_logger()
    logger.info(f"Starting daily incremental load for table: {table}")
    
    con = None
    try:
        con = duckdb.connect(db_path)
        today_date = datetime.now().date()
        query = f"SELECT max(visit_date) FROM {table}"
        latest_date_in_db = con.execute(query).fetchone()[0]
        
        latest_successful_date_in_db = None
        differences = (today_date - latest_date_in_db).days
        logger.info(f"Checking for new data. Days to check: {differences}")

        if differences <= 0:
            logger.info(f"No new days to load. Database is up to date as of {latest_date_in_db}.")
            return

        for day in range(1, differences + 1):
            date_to_load = latest_date_in_db + timedelta(days=day)
            day_url = url_prefix + date_to_load.strftime("%Y-%m-%d") + ".parquet"
            query = f"INSERT INTO {table} SELECT * FROM read_parquet('{url_prefix}')"
            logger.info(f"Starting to load data for date: {date_to_load}")

            try:
                con.execute(query)
                logger.info(f"Successfully loaded data for date {date_to_load}")
                latest_successful_date_in_db = date_to_load
            except duckdb.IOException:
                logger.warning(f"Data for date {date_to_load} is not available yet.")
                break
            except Exception as e:
                logger.error(f"Failed to load data for {date_to_load}: {e}")
                break

        if latest_successful_date_in_db:
            logger.info(f"Successfully loaded new data up to {latest_successful_date_in_db}")
        else:
            logger.info(f"No new data was loaded.")
            
    except Exception as e:
        logger.error(f"Daily incremental load failed: {e}")
        raise
    finally:
        if con:
            con.close()

@task(retries=2, retry_delay_seconds=5)
def send_telegram_report_task(db_path: str, bot_token: str, channel_id: str):
    """
    Generates a graph of monthly donations and sends it to Telegram.
    """
    logger = get_run_logger()
    logger.info("Starting Telegram report task...")
    
    con = None
    try:
        year = datetime.now().year
        con = duckdb.connect(db_path)

        query = f"""
            SELECT MONTH(visit_date) as Month, count(*) as daily_donations 
            FROM historical 
            WHERE YEAR(visit_date) = {year} 
            GROUP BY Month ORDER BY Month ASC
        """
        data_df = con.execute(query).df()
        
        if data_df.empty:
            logger.warning(f"No data found for year {year}. Skipping report.")
            return

        plt.figure()
        data_df.plot(kind="line", x="Month", y="daily_donations", marker='o')
        plt.title(f"Monthly Donations for {year}")
        plt.ylabel("Total Donations")
        plt.xlabel("Month")
        plt.xticks(data_df["Month"])
        plt.grid(True)
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        plt.close()

        bot = telebot.TeleBot(bot_token)
        caption = f"Monthly report for {year} (as of {datetime.now().strftime('%Y-%m-%d')})."
        logger.info(f"Sending plot to Telegram channel {channel_id}...")
        bot.send_photo(channel_id, photo=buffer, caption=caption)
        logger.info("Telegram report sent successfully!")

    except Exception as e:
        logger.error(f"Telegram report task failed: {e}")
        raise
    finally:
        if con:
            con.close()

# --- Flow Definition ---

@flow(name="ETL - Incremental Blood Donation Load and Report", log_prints=True)
def incremental_load_flow():
    """
    Main ETL flow:
    1. Reloads retention data.
    2. Reloads donor rate data.
    3. Incrementally loads daily historical data.
    4. Sends a Telegram report if all loads are successful.
    """
    logger = get_run_logger()
    
    env_path = find_dotenv()
    if env_path:
        logger.info(f"Loading environment variables from {env_path}")
        load_dotenv(env_path)
    else:
        logger.warning("No .env file found. Relying on system environment variables.")

    db_path = os.getenv("DUCKDB_FILE_PATH")
    daily_url = os.getenv("DAILY_PARQUET_URL")
    retention_url = os.getenv("RETENTION_PARQUET_URL")
    donnorrate_url = os.getenv("RATE_PARQUET_URL")
    bot_token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")
    
    if not all([db_path, daily_url, retention_url, donnorrate_url, bot_token, channel_id]):
        logger.error("Missing environment variables. Flow cannot run.")
        return

    # Run data load tasks
    load_data_to_db(retention_url, 'retention', db_path)
    load_data_to_db(donnorrate_url, 'donorrate', db_path)
    load_incremental_daily(daily_url, 'historical', db_path)

    # Run report task (depends on successful completion of the above)
    logger.info("Data loads complete. Starting Telegram report.")
    send_telegram_report_task(db_path, bot_token, channel_id)

    logger.info("Incremental load and report flow finished successfully.")

# --- Deployment Definition & Execution ---
# This block now SERVES the flow, replacing the need for an agent.

if __name__ == "__main__":
    
    # 1. Define the deployment and serve it.
    # This single command registers the flow with the server
    # and starts a worker for it at the same time.
    incremental_load_flow.serve(
        name="daily-blood-data-deployment",  # The name of the deployment
        
        # 2. Set the schedule for every 10 minutes
        cron="*/10 * * * *",
        
        # 3. Set the work pool (the default pool agents listen to)
        # work_pool_name="default-pool"
    )
    
    # When you run `python etl_flow.py`, this code will start
    # and it will connect to your Prefect server and begin
    # executing the flow every 10 minutes.