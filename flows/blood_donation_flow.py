from dotenv import load_dotenv, find_dotenv

from prefect import flow
from prefect.logging import get_run_logger
import os
import datetime 

from tasks.etl_task import load_transformed_donorrate_to_db,load_incremental_daily,load_transformed_retention_to_db
from tasks.telegram_task import send_update_new_data_loaded,send_graphs

from tasks.graph_task import generate_heatmap_retention,generate_age_gender_boxplot,generate_age_histogram,generate_blood_group_line_graph,calculate_retention

 
@flow(name=f"ETL-Blood Donation ", log_prints=True)
def etl_blood_donation_flow():
    try:
        logger = get_run_logger()

        env_path = find_dotenv()
        load_dotenv(env_path)

        db_path = os.getenv("DUCKDB_FILE_PATH")
        daily_url = os.getenv("DAILY_PARQUET_URL")

        bot_token = os.getenv("BOT_TOKEN")
        channel_id = os.getenv("CHANNEL_ID")

    
        retention_url = os.getenv("RETENTION_PARQUET_URL")
        donorrate_url = os.getenv("RATE_PARQUET_URL")
  

        retention_total_new_data = load_transformed_retention_to_db(retention_url,'retention', db_path) 
        donorrate_total_new_data = load_transformed_donorrate_to_db(donorrate_url,'donorrate', db_path) 
        daily_total_new_data_insert,latest_date_in_db = load_incremental_daily(daily_url,"historical",db_path)


        update_summary = {
            "Retention":retention_total_new_data,
            "Donor Rate": donorrate_total_new_data,
            "Historical Data": daily_total_new_data_insert
        }
        
        send_update_new_data_loaded(update_summary,bot_token,channel_id,latest_date_in_db)

        # send graph start
        rate_retention = calculate_retention(db_path,'retention')

        heatmap = generate_heatmap_retention(rate_retention)
        linegraph = generate_blood_group_line_graph(db_path,'historical')
        histogram = generate_age_histogram(db_path,'donorrate')
        boxplot = generate_age_gender_boxplot(db_path,'donorrate')

        send_graphs(bot_token,channel_id,heatmap,linegraph,histogram,boxplot)


    except Exception as e:
        logger.error(f"Failed because: {e}")

if __name__ == "__main__":

    etl_blood_donation_flow.serve(
        name=f"daily-blood-data-deployment",
        
        #  every 10 minutes
        # cron="*/10 * * * *",
    )