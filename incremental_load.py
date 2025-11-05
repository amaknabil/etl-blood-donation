import os
import duckdb
from dotenv import load_dotenv,find_dotenv
from datetime import datetime,timedelta

env_path = find_dotenv()
load_dotenv(env_path)


# daily_url = os.getenv("COMPLETE_PARQUET_URL")
db_path = os.getenv("DUCKDB_FILE_PATH") 

url = os.getenv("DAILY_PARQUET_URL")
today_date = datetime.now().date()
today_dates = datetime.now().strftime("%Y-%m-%d")


try:
    con = duckdb.connect(db_path);
    query = f"select max(visit_date) from historical"
    latest_date_in_db = con.execute(query).fetchone()[0]
    latest_date = latest_date_in_db
    latest_successful_date_in_db = None

    differences = (today_date - latest_date_in_db).days
 
    print("\n")
    for day in range(differences):
        latest_date_in_db = (latest_date_in_db + timedelta(days=1))
        day_url = url + latest_date_in_db.strftime("%Y-%m-%d") + ".parquet"
        # print(day_url)
        query = f"INSERT INTO historical SELECT * FROM read_parquet('{day_url}')"
        print(f"Starting to load data for date: {latest_date_in_db}")

        try:
            con.execute(query)
            print(f"successfully load data into historical table for date {latest_date_in_db}\n")
            latest_successful_date_in_db = latest_date_in_db
        except duckdb.IOException as e:
            print(f"Data for date :{latest_date_in_db} is still not available\n")
        except Exception as e:
            print(f"Fail on {latest_date_in_db} because: {e}")

    if(not(latest_successful_date_in_db)):
        print(f"There is no new data loaded, latest data is still on {latest_date}")
    else:
        print(f"successfully load data into historical table from {(latest_date + timedelta(days=1))} to {latest_successful_date_in_db}")
    con.close()
    


except Exception as e:
    print(f"Fail on {latest_date_in_db} because: {e}")

