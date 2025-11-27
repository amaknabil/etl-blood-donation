from prefect import task
from prefect.logging import get_run_logger

import telebot
import matplotlib.pyplot as plt
import io

import duckdb
from datetime import datetime

@task(retries=2, retry_delay_seconds=5)
def send_update_new_data_loaded(updates: dict, bot_token: str, channel_id: str):
    logger = get_run_logger()
    bot = telebot.TeleBot(bot_token)
    
    # 1. Create a Header with a Timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message_lines = [f"<b>ETL Pipeline Execution Report</b>"]
    message_lines.append(f"<i>{current_time}</i>\n")
    
    # 2. Loop through the dictionary of updates to build the body
    total_rows = 0
    for table_name, count in updates.items():
        total_rows += count

        message_lines.append(f"<b>{table_name.title()}:</b> <code>+{count} rows</code>")

    # 3. Add a Footer summary
    message_lines.append(f"\n<b>Total New Records:</b> {total_rows}")

    # Join all lines into one string
    final_message = "\n".join(message_lines)

    try:
        # IMPORTANT: Set parse_mode to 'HTML'
        bot.send_message(channel_id, text=final_message, parse_mode='HTML')
        logger.info("Consolidated Telegram report sent successfully.")
    except Exception as e:
        logger.error(f"Telegram report task failed: {e}")
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