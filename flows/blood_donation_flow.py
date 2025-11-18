from dotenv import load_dotenv, find_dotenv

from prefect import flow
from prefect.logging import get_run_logger
import os
import datetime 

from tasks.etl_task import load_data_to_db,load_incremental_daily
from tasks.telegram_task import send_daily_report,send_update_incremental
x = datetime.datetime.now()

@flow(name=f"ETL-Blood Donation - {x}", log_prints=True)
def etl_blood_donation_flow():
    try:
        logger = get_run_logger()

        env_path = find_dotenv()
        load_dotenv(env_path)

        db_path = os.getenv("DUCKDB_FILE_PATH")
        daily_url = os.getenv("DAILY_PARQUET_URL")

        bot_token = os.getenv("BOT_TOKEN")
        channel_id = os.getenv("CHANNEL_ID")

        table = {
            "retention":os.getenv("RETENTION_PARQUET_URL"),
            "donorrate":os.getenv("RATE_PARQUET_URL")
        }

        # load data
        for table_name,url in table.items():
            total_new_data = load_data_to_db(url,table_name, db_path) 
            send_update_incremental(table_name,total_new_data,bot_token,channel_id)
        
        total_new_data_insert = load_incremental_daily(daily_url,"historical",db_path)
        send_update_incremental("historical",total_new_data_insert,bot_token,channel_id)
        send_daily_report(db_path,bot_token,channel_id)
    except Exception as e:
        logger.error(f"Failed because: {e}")

if __name__ == "__main__":

    etl_blood_donation_flow.serve(
        name=f"daily-blood-data-deployment- {x}",
        
        #  every 10 minutes
        cron="*/10 * * * *",
    )