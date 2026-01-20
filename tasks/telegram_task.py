from prefect import task
from prefect.logging import get_run_logger

import telebot
from telebot.types import InputMediaPhoto
import matplotlib.pyplot as plt
import io
import pandas as pd

import duckdb
from datetime import datetime, timedelta, timezone

@task(retries=2, retry_delay_seconds=5)
def send_update_new_data_loaded(updates: dict, bot_token: str, channel_id: str, latest_date_in_db):
    logger = get_run_logger()
    bot = telebot.TeleBot(bot_token)
    
  
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message_lines = [f"<b>ETL Pipeline Report</b>"]
    message_lines.append(f"<i>{current_time}</i>\n")

    total_rows = 0
    for table_name, count in updates.items():
        total_rows += count
        message_lines.append(f"<b>{table_name.title()}:</b> <code>+{count} rows</code>")

 
    formatted_date = latest_date_in_db.strftime("%d %b %Y") if latest_date_in_db else "N/A"
    
    message_lines.append(f"\n<b>Data Up To:</b> <code>{formatted_date}</code>")
    message_lines.append(f"<b>Total New Records:</b> {total_rows}")

    
    if total_rows > 0:
        message_lines.insert(0, "<b>New Data Loaded Successfully!</b>")
    else:
        message_lines.insert(0, "<b>No New Data Found</b>")

    final_message = "\n".join(message_lines)

    try:
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

@task
def send_graphs(bot_token: str, channel_id: str, *graphs):
    """
    Sends a dynamic number of graphs as a single album (MediaGroup) using telebot.
    
    Usage: send_graphs_dynamic(token, channel, plot1, plot2, plot3, ...)
    """
    logger = get_run_logger()
    
    try:
        # 1. Initialize Bot
        bot = telebot.TeleBot(bot_token)
        
        # 2. Prepare Media Group
        media_group = []
        
        # Enumerate gives us an index (0, 1, 2...) to help with logic
        for index, graph_buffer in enumerate(graphs):
            # Safety check: Ensure the buffer is at the start
            if isinstance(graph_buffer, io.BytesIO):
                graph_buffer.seek(0)
            
            # Create the Photo object
            # We explicitly allow 'None' captions for all except the first one (optional)
            photo = InputMediaPhoto(graph_buffer)
            
            # 3. Add a caption only to the very first image
            if index == 0:
                photo.caption = (
                    f"📊 **Analytics Report**\n"
                    f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"Contains {len(graphs)} charts."
                )
                photo.parse_mode = 'Markdown'
            
            media_group.append(photo)

        # 4. Send
        if media_group:
            bot.send_media_group(chat_id=channel_id, media=media_group)
            logger.info(f"✅ Successfully sent {len(media_group)} graphs to channel {channel_id}")
        else:
            logger.warning("⚠️ No graphs were provided to send.")

    except Exception as e:
        logger.error(f"❌ Failed to send telegram message: {e}")
        # We don't raise here if we want the flow to finish even if notification fails
        # raise e


@task(retries=3, retry_delay_seconds=10)
def send_fail_notification(bot_token: str, channel_id: str, error):
    logger = get_run_logger()
    
    try:
        bot = telebot.TeleBot(bot_token)
    
        utc_now = datetime.now(timezone.utc)
        gmt8_time = utc_now + timedelta(hours=8)
        formatted_time = gmt8_time.strftime("%Y-%m-%d %H:%M:%S (GMT+8)")

        error_message = str(error)
        
        # Format the message with HTML
        message_text = (
            f"<b>Task Failed</b>\n\n"
            f"<b>Time:</b> <code>{formatted_time}</code>\n\n"
            f"<b>Error:</b> <pre>{error_message}</pre>"
        )
        
        # Send the message
        bot.send_message(channel_id, message_text, parse_mode='HTML')
        logger.info(f"Failure notification sent to channel {channel_id}")
        
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        pass

