from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta
from prefect import flow
from prefect.logging import get_run_logger
import os
from tasks.etl_task import load_data_to_db, check_available_daily_data,check_available_other_data, get_latest_date_in_db, load_data_to_db_donorrate
from tasks.telegram_task import send_update_new_data_loaded,send_graphs,send_fail_notification
from tasks.graph_task import generate_heatmap_retention,generate_age_gender_boxplot,generate_age_histogram,generate_blood_group_area_graph,calculate_retention,generate_donor_heatmap_demographic
from prefect.client.schemas.schedules import CronSchedule

@flow(retries=3,retry_delay_seconds=10,name=f"ETL-Blood Donation ", log_prints=True)
def etl_blood_donation_flow():
    bot_token = None
    channel_id = None
    logger = get_run_logger()
    try:
        env_path = find_dotenv()
        load_dotenv(env_path)

        db_path = os.getenv("DUCKDB_FILE_PATH")
        daily_url = os.getenv("DAILY_PARQUET_URL")

        bot_token = os.getenv("BOT_TOKEN")
        channel_id = os.getenv("CHANNEL_ID")

    
        retention_url = os.getenv("RETENTION_PARQUET_URL")
        donorrate_url = os.getenv("RATE_PARQUET_URL")
        config = {
            "memory_limit": "450MB",  
            "temp_directory": "duck_temp",
            "threads": 1, 
            "preserve_insertion_order": False
        }

        yesterday = datetime.now().date() - timedelta(days=1)
        latest_date_db = get_latest_date_in_db(db_path,"historical",config)

        # check data freshness
        # if latest_date_db == yesterday:
        #     logger.info("Data is already updated. No action needed.")
        #     return
  
        check_available_daily_data(daily_url,db_path,"historical",config,channel_id,bot_token)
        # check_available_other_data(retention_url,db_path,"retention",config)
        # check_available_other_data(donorrate_url,db_path,"donorrate",config)


        daily_total_new_data_insert,latest_date_in_db = load_data_to_db(daily_url,"historical",db_path,config)
        retention_total_new_data,latest_date_in_db_retention = load_data_to_db(retention_url,'retention', db_path,config) 
        donorrate_total_new_data= load_data_to_db_donorrate(donorrate_url,"donorrate",db_path,config)
        
        update_summary = {
            "Retention":retention_total_new_data,
            "Donor Rate": donorrate_total_new_data,
            "Historical Data": daily_total_new_data_insert
        }

        # send graph start
        rate_retention = calculate_retention(db_path,'retention',1,config)

        heatmap = generate_heatmap_retention(rate_retention)
        linegraph = generate_blood_group_area_graph(db_path,'historical',config)
        demographic = generate_donor_heatmap_demographic(db_path,config)

        send_update_new_data_loaded(update_summary,bot_token,channel_id,latest_date_in_db)
        send_graphs(bot_token,channel_id,heatmap,linegraph,demographic)

    except Exception as e:
        logger.error(f"Flow failed because: {e}")
        
        if bot_token and channel_id:
            send_fail_notification(bot_token, channel_id, e)
        else:
            logger.error("Could not send failure notification due to missing bot_token or channel_id")
        raise

if __name__ == "__main__":

    etl_blood_donation_flow.serve(
        name=f"daily-blood-data-deployment",
        schedule=CronSchedule(
            cron="0 8 * * *", 
            timezone="Asia/Kuala_Lumpur"
        )
        

        )
 