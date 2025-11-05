import os
import duckdb
from dotenv import load_dotenv,find_dotenv
from datetime import datetime,timedelta

env_path = find_dotenv()
load_dotenv(env_path)


# daily_url = os.getenv("COMPLETE_PARQUET_URL")
db_path = os.getenv("DUCKDB_FILE_PATH") 

daily_url = os.getenv("DAILY_PARQUET_URL")
retention_url = os.getenv("RETENTION_PARQUET_URL")
donnorrate_url = os.getenv("RATE_PARQUET_URL")


#retention and donorrate
def load_data_to_db(con,url,table):
    try:
        print(f"Incremental load for table {table}")

        #delete old table
        query = f"DELETE FROM {table}"
        print(f"1 - Deleting table {table}....")
        con.execute(query)
        con.commit()
        print(f"Successfully deleted table {table}.\n")

        #insert new data into new table
        query = f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}')"
        print(f"2 - Starting to loading data into {table} table")
        con.execute(query)
        print(f"Successfully loaded data into {table} histocial\n")
    except Exception as e:
        print(f"Fail to load on table {table} because : {e}")


#daily load
def load_incremental_daily(con,url,table):
    today_date = datetime.now().date()
    query = f"select max(visit_date) from {table}"
    latest_date_in_db = con.execute(query).fetchone()[0]
    latest_date = latest_date_in_db
    latest_successful_date_in_db = None

    differences = (today_date - latest_date_in_db).days
 
    print("\n")
    for day in range(differences):
        latest_date_in_db = (latest_date_in_db + timedelta(days=1))
        day_url = url + latest_date_in_db.strftime("%Y-%m-%d") + ".parquet"
        query = f"INSERT INTO {table} SELECT * FROM read_parquet('{day_url}')"
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


try:
    print(f"Connecting to {db_path}")
    con = duckdb.connect(db_path)
    print(f"Successfully connected to {db_path}\n")

    load_data_to_db(con,retention_url,'retention')
    load_data_to_db(con,donnorrate_url,'donorrate')
    load_incremental_daily(con,daily_url,'historical')

    print("Successfully done incremental load")
    con.close()
    print("DB Closed")
    
except Exception as e:
    print(f"Fail because: {e}")

