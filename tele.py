import telebot
from dotenv import load_dotenv,find_dotenv
import os
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import io

env_path = find_dotenv()

load_dotenv(env_path)


BOT_TOKEN = os.getenv("BOT_TOKEN")

CHANNEL_ID = os.getenv("CHANNEL_ID")

# --- Create the Bot object ---
bot = telebot.TeleBot(BOT_TOKEN) # <-- 2. Create the bot object

try:
    year = datetime.now().year

    con = duckdb.connect("blood_data.duckdb")

    query = f"select YEAR(visit_date) as Year,MONTH(visit_date) as Month, count(*) as daily_donations from historical where YEAR(visit_date) = {year} group by YEAR(visit_date),MONTH(visit_date) order by YEAR(visit_date) ASC"

    data_df = con.execute(query).df()

    con.close()

    plt.figure() # Create a new figure
    data_df.plot(kind="line", x="Month", y="daily_donations", marker='o')
    
    # Make the plot look nice
    plt.title(f"Monthly Donations for {year}")
    plt.ylabel("Total Donations")
    plt.xlabel("Month")
    plt.xticks(data_df["Month"]) # Ensure ticks are on the month numbers
    plt.grid(True)
    
    # --- 3. Save Plot to In-Memory Buffer ---
    # Create a buffer to hold the image's binary data
    buffer = io.BytesIO()
    
    # Save the plot into the buffer in PNG format
    plt.savefig(buffer, format='png')
    
    # "Rewind" the buffer to the beginning so telebot can read it
    buffer.seek(0)


    print(f"Sending text to {CHANNEL_ID}...")
    bot.send_message(CHANNEL_ID, 
                     text="Hello! This is your daily message.")
    
    print(f"Sending photo to {CHANNEL_ID}...")
    bot.send_photo(CHANNEL_ID, 
                   photo=buffer,  
                   caption="Here is your daily photo!")     
    
    print("Messages sent successfully!")
    plt.close()

except Exception as e:
    print(f"An error occurred: {e}")



