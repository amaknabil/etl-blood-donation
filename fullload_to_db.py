import os
import duckdb
from dotenv import load_dotenv,find_dotenv

env_path = find_dotenv()
load_dotenv(env_path)

historical_url = os.getenv("COMPLETE_PARQUET_URL")
retention_url = os.getenv("RETENTION_PARQUET_URL")
donnorrate_url = os.getenv("RATE_PARQUET_URL")

db_path = os.getenv("DUCKDB_FILE_PATH") 

def load_data_to_db(con,url,table):
    query = f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}')"
    print(f"Starting to loading data into {table} table")
    con.execute(query)
    print(f"Successfully loaded data into {table} histocial\n")

try:
    print(f"Connecting to {db_path}")
    con = duckdb.connect(db_path)
    print(f"Successfully connected to {db_path}\n")
    load_data_to_db(con,historical_url,'historical')
    load_data_to_db(con,retention_url,'retention')
    load_data_to_db(con,donnorrate_url,"donorrate")

    print("Successfully load all data to each tables")

    con.close()
    print("close db")

except Exception as e:
    print(f"Fail because: {e}")