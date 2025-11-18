from prefect import task
from prefect.logging import get_run_logger

import telebot
import matplotlib.pyplot as plt
import io

import duckdb
from datetime import datetime

@task(retries=2, retry_delay_seconds=5)
def send_update_incremental(table:str , total_new_data:int, bot_token:str ,channel_id:str):
    logger = get_run_logger()

    bot = telebot.TeleBot(bot_token)

    caption = f"Update for table:{table} \n Total new data: +{total_new_data}"

    try:
        bot.send_message(channel_id, text=caption)
    except Exception as e:
        logger.error(f"Telegram report task failed for table {table} because \n: {e}")
        raise


@task(retries=2, retry_delay_seconds=5)
def send_daily_report(db_path:str,bot_token:str,channel_id:str):
    con = None
    logger = get_run_logger()
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